"""ADK 공통 런타임: 환경 설정, 모델, 사용량 플러그인, 요청 상태 레지스트리, 노드 호출 헬퍼.

- ADK import 전에 span 내용 기록을 끈다(스파이크 7: 켜 두면 프롬프트 원문이 trace에 실림).
- 세션 상태(ctx.state)는 deepcopy되므로 큰 입력은 세션 id로 찾는 프로세스 내 레지스트리에 둔다.
"""
import os
import time
from typing import Any, Dict, List

from app.configs.settings import settings

os.environ.setdefault("ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS", "false")
os.environ.setdefault("GOOGLE_API_KEY", settings.gemini_api_key)
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "false")

from google.adk.models import Gemini  # noqa: E402
from google.adk.plugins.base_plugin import BasePlugin  # noqa: E402
from google.adk.workflow import node  # noqa: E402
from google.genai import types  # noqa: E402

MODEL_NAME = "gemini-2.5-flash"

# 프로세스 내 요청 상태: session_id → 엔진별 상태 객체
STATES: Dict[str, Any] = {}
USAGE: Dict[str, List[dict]] = {}
MODEL_ERRORS: Dict[str, List[dict]] = {}


def make_model() -> Gemini:
    # HTTP 5xx/429 재시도: 기존 tenacity 설정(3회, 2~10초 지수 백오프)과 같은 값
    return Gemini(
        model=MODEL_NAME,
        retry_options=types.HttpRetryOptions(attempts=3, initial_delay=2, max_delay=10, exp_base=2),
    )


class UsagePlugin(BasePlugin):
    """LLM 호출마다 사용량을 세션별로 모은다(EngineResult.usage)."""

    def __init__(self):
        super().__init__(name="usage_plugin")
        self._t0: Dict[tuple, float] = {}

    async def before_model_callback(self, *, callback_context, llm_request):
        self._t0[(callback_context.session.id, callback_context.agent_name)] = time.perf_counter()
        return None

    async def after_model_callback(self, *, callback_context, llm_response):
        um = llm_response.usage_metadata
        if um is None or llm_response.partial:
            return None
        t0 = self._t0.pop((callback_context.session.id, callback_context.agent_name), None)
        USAGE.setdefault(callback_context.session.id, []).append({
            "node": callback_context.agent_name,
            "model": llm_response.model_version or MODEL_NAME,
            "input": um.prompt_token_count or 0,
            "cached": um.cached_content_token_count or 0,
            "output": um.candidates_token_count or 0,
            "thinking": um.thoughts_token_count or 0,
            "ms": int((time.perf_counter() - t0) * 1000) if t0 else None,
        })
        return None

    async def on_model_error_callback(self, *, callback_context, llm_request, error):
        # DynamicNodeFailError는 원인을 감추므로 모델 오류를 따로 남긴다
        MODEL_ERRORS.setdefault(callback_context.session.id, []).append({
            "type": "model_error", "node": callback_context.agent_name, "error": f"{type(error).__name__}: {str(error)[:300]}",
        })
        return None


def _cause(e: BaseException) -> str:
    chain, cur = [], e
    while cur is not None and len(chain) < 4:
        chain.append(f"{type(cur).__name__}: {str(cur)[:160]}")
        cur = cur.__cause__ or cur.__context__
    return " <- ".join(chain)


async def call_agent(ctx, state, agent, text: str, timeout: float) -> Any:
    """동적 노드로 에이전트를 실행한다. 실패하면 오류를 알려 주고 그 노드만 1회 다시 만든다(§6.3).

    재시도할 시간이 없으면(남은 시간 < timeout) 재시도하지 않는다. 최종 실패는 예외로 올린다.
    """
    last: BaseException | None = None
    for attempt in (1, 2):
        if attempt == 2 and state.remaining() < timeout:
            state.events.append({"type": "retry_skipped", "node": agent.name, "reason": "deadline"})
            break
        prompt = text if attempt == 1 else (
            f"{text}\n\n[재요청] 이전 응답이 실패했다({str(last)[:200]}). 출력 스키마와 개수 제한을 정확히 지켜 다시 작성하라."
        )
        t0 = time.monotonic()
        try:
            out = await ctx.run_node(node(agent, timeout=timeout), prompt, run_id=f"{agent.name}-a{attempt}")
            if attempt == 2:
                state.events.append({"type": "recovered", "node": agent.name})
            return out
        except Exception as e:  # noqa: BLE001 - 노드 실패는 모두 같은 규칙으로 처리
            last = e
            elapsed = time.monotonic() - t0
            state.events.append({
                "type": "retry" if attempt == 1 else "node_failed",
                "node": agent.name,
                # DynamicNodeFailError는 원인을 감춘다. 경과 시간이 timeout에 닿았으면 timeout으로 본다
                "error": "timeout" if elapsed >= timeout * 0.95 else _cause(e),
                "elapsed_s": round(elapsed, 1),
            })
    raise RuntimeError(f"{agent.name} 실패: {_cause(last) if last else 'deadline'}")
