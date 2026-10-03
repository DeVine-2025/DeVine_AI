"""V1: 회의 자료 구조(S9~S12)를 ADK Workflow로 구현한 엔진.

    prep(코드: 기여 원장·파일/커밋 ID·청크)
      ├─ map_stage   : 청크별 근거 카드(LLM, 병렬 N개)
      └─ tech_stage  : 기술스택 에이전트(LLM, 빌드 파일 + 수정 파일 목록만)
    join → verify_stage(코드: 카드 병합·근거 검증·blame 보정)
      ├─ features_stage : 기능 에이전트 → implementedFeatures, projectSummary, purpose
      └─ insights_stage : 인사이트 에이전트 → codeInsights, improvements, nextSteps, architecturePattern
    join → main_stage(LLM, detail만 입력) → assemble_stage(코드)

실패 처리(§6.3, §8.2): 노드 1회 재생성 → Map 실패 청크가 50% 초과이거나 섹션 작성 실패면
남은 시간이 60초 이상일 때 legacy 단일 호출로 폴백, 아니면 FAILED. 기술스택 실패는 techstacks 없이 진행한다.
"""
import asyncio
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.report.context import ReportContext
from app.report.engines import adk_runtime as rt
from app.report.engines.base import EngineResult
from app.report.engines.shared import prompts as sp
from app.report.engines.shared.assemble import assemble, detail_view
from app.report.engines.shared.evidence import VerifiedFeature, verify_and_merge
from app.report.engines.shared.schemas import card_model, features_model, insights_model, main_model, tech_model
from app.report.engines.v1.chunking import Chunk, EvidenceIndex, build_chunks, build_index
from app.report.engines.v1.ledger import Ledger, compute_ledger, refine_with_blame
from app.report.engines.v1.prompts import map_instruction
from app.report.errors import ReportGenerationError

from google.adk.agents import LlmAgent  # noqa: E402
from google.adk.apps import App  # noqa: E402
from google.adk.runners import Runner  # noqa: E402
from google.adk.sessions import InMemorySessionService  # noqa: E402
from google.adk.workflow import JoinNode, Workflow, node  # noqa: E402
from google.genai import types  # noqa: E402

logger = logging.getLogger(__name__)

APP_NAME = "devine_report_v1"
TOTAL_DEADLINE = 110.0
FALLBACK_MIN_REMAINING = 60.0
TIMEOUTS = {"map": 60.0, "tech": 45.0, "features": 45.0, "insights": 45.0, "main": 30.0}
# 에이전트별 thinking 상한(회의 자료 2단계 작업 항목). 기본값(동적)은 Map 한 번에 thinking 최대 9천 토큰,
# 40~50초가 걸려 2분 제약을 넘었다(haru-web 1회 실측). 추출 성격인 Map·기술스택은 낮게, 작성 섹션은 조금 높게 둔다.
THINKING_BUDGET = {"map": 1024, "tech": 512, "features": 2048, "insights": 2048, "main": 1024}
MAP_CONCURRENCY = 10  # = 최대 청크 수. 청크가 대기하면 Map 단계가 두 배로 길어진다
MAP_FAIL_RATIO = 0.5
_FID = re.compile(r"\bF\d+\b")


@dataclass
class V1State:
    ctx: ReportContext
    deadline: float
    events: List[dict] = field(default_factory=list)
    ledger: Optional[Ledger] = None
    idx: Optional[EvidenceIndex] = None
    chunks: List[Chunk] = field(default_factory=list)
    cards: List[dict] = field(default_factory=list)
    tech: Optional[dict] = None
    feats: List[VerifiedFeature] = field(default_factory=list)
    features: Optional[dict] = None
    insights: Optional[dict] = None
    main: Optional[dict] = None
    result: Optional[tuple] = None
    fallback: Optional[str] = None
    error: Optional[ReportGenerationError] = None

    def remaining(self) -> float:
        return self.deadline - time.monotonic()

    @property
    def stopped(self) -> bool:
        return bool(self.fallback or self.error)


def _state(ctx) -> V1State:
    return rt.STATES[ctx.session.id]


def _agent(name: str, kind: str, instruction: str, schema) -> LlmAgent:
    return LlmAgent(
        name=name,
        model=rt.make_model(),
        instruction=instruction,
        output_schema=schema,
        generate_content_config=types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_budget=THINKING_BUDGET[kind])
        ),
    )


# ---- 노드 ----

async def prep_stage(ctx, node_input):
    st = _state(ctx)
    c = st.ctx

    def _prep():
        ledger = compute_ledger(c.dir_path, c.author_name, c.author_emails, c.rename_map, c.head_file_set)
        idx = build_index(c, [o.path for o in ledger.other_owned])
        chunks, info = build_chunks(c, idx)
        return ledger, idx, chunks, info

    st.ledger, st.idx, st.chunks, info = await asyncio.to_thread(_prep)
    st.chunks = [ch for ch in st.chunks if ch.file_ids]
    st.events.append({"type": "chunks", **info, "usable": len(st.chunks),
                      "format_commits_excluded": st.ledger.excluded_format_commits})
    if not st.chunks:
        st.error = ReportGenerationError("no_evidence", "HEAD에 남은 작성자 파일이 없어 근거를 만들 수 없습니다")
    return {"chunks": len(st.chunks)}


async def map_stage(ctx, node_input):
    st = _state(ctx)
    if st.stopped:
        return None
    sem = asyncio.Semaphore(MAP_CONCURRENCY)
    instruction = map_instruction(st.ctx.author_name)

    async def one(ch: Chunk):
        agent = _agent(f"map_{ch.chunk_id}", "map", instruction, card_model(ch.file_ids, ch.commit_ids))
        async with sem:
            try:
                return await rt.call_agent(ctx, st, agent, ch.text, TIMEOUTS["map"])
            except Exception:  # noqa: BLE001 - 청크 실패는 격리하고 비율로 판단
                return None

    cards = await asyncio.gather(*[one(ch) for ch in st.chunks])
    failed = sum(1 for c in cards if c is None)
    st.cards = [c for c in cards if c]
    st.events.append({"type": "map_done", "chunks": len(cards), "failed": failed})
    if cards and failed / len(cards) > MAP_FAIL_RATIO:
        st.fallback = f"map_failed({failed}/{len(cards)})"
    return {"cards": len(st.cards)}


async def tech_stage(ctx, node_input):
    st = _state(ctx)
    if st.stopped:
        return None
    c = st.ctx
    agent = _agent("tech", "tech", sp.TECH_INSTRUCTION, tech_model(c.available_techstacks))
    try:
        st.tech = await rt.call_agent(ctx, st, agent, sp.format_tech_input(c, st.ledger), TIMEOUTS["tech"])
    except Exception as e:  # noqa: BLE001
        st.events.append({"type": "tech_degraded", "error": str(e)[:200]})
    return {"tech": st.tech is not None}


async def verify_stage(ctx, node_input):
    st = _state(ctx)
    if st.stopped:
        return None
    feats, stats = verify_and_merge(st.cards, st.idx, st.ledger)
    blamed = await asyncio.to_thread(
        refine_with_blame, st.ctx.dir_path, st.ledger, [p for f in feats for p in f.paths], st.ctx.author_name, st.ctx.author_emails
    )
    # blame으로 수준이 바뀌었을 수 있으니 기능 수준을 다시 계산
    feats, stats2 = verify_and_merge(st.cards, st.idx, st.ledger)
    st.feats = feats
    st.events.append({"type": "verify", **stats, "features": len(feats), "blame_level_changed": blamed})
    if not feats:
        st.error = ReportGenerationError("no_evidence", "근거가 확인된 기능이 없습니다")
    return {"features": len(feats)}


async def features_stage(ctx, node_input):
    st = _state(ctx)
    if st.stopped:
        return None
    c = st.ctx
    schema = features_model([f.fid for f in st.feats], list(st.idx.other_ids))
    agent = _agent("features", "features", sp.FEATURES_INSTRUCTION, schema)
    try:
        st.features = await rt.call_agent(ctx, st, agent, sp.format_features_input(c, st.feats, st.ledger, st.idx), TIMEOUTS["features"])
    except Exception:  # noqa: BLE001
        st.fallback = st.fallback or "features_failed"
    return {"ok": st.features is not None}


async def insights_stage(ctx, node_input):
    st = _state(ctx)
    if st.stopped:
        return None
    c = st.ctx
    obs: Dict[str, List[str]] = {"patterns": [], "risks": [], "notes": []}
    for card in st.cards:
        for k in obs:
            obs[k] += card.get(k, []) or []
    fids = {fid for f in st.feats for fid in f.file_ids}
    fids |= {m for v in obs.values() for o in v for m in _FID.findall(o) if m in st.idx.file_ids}
    agent = _agent("insights", "insights", sp.INSIGHTS_INSTRUCTION, insights_model(sorted(fids, key=lambda x: int(x[1:]))))
    try:
        st.insights = await rt.call_agent(ctx, st, agent, sp.format_insights_input(c, st.feats, st.ledger, st.idx, obs), TIMEOUTS["insights"])
    except Exception:  # noqa: BLE001
        st.fallback = st.fallback or "insights_failed"
    return {"ok": st.insights is not None}


async def main_stage(ctx, node_input):
    st = _state(ctx)
    if st.stopped:
        return None
    by_fid = {f.fid: f for f in st.feats}
    used = [f.get("fid") for cat in st.features.get("categories", []) for f in cat.get("features", []) if f.get("fid") in by_fid]
    agent = _agent("main", "main", sp.MAIN_INSTRUCTION, main_model(list(dict.fromkeys(used)) or list(by_fid)))
    view = detail_view(st.features, st.insights, by_fid)
    try:
        st.main = await rt.call_agent(ctx, st, agent, sp.format_main_input(st.ctx, view), TIMEOUTS["main"])
    except Exception:  # noqa: BLE001
        st.fallback = st.fallback or "main_failed"
    return {"ok": st.main is not None}


async def assemble_stage(ctx, node_input):
    st = _state(ctx)
    if st.stopped:
        return None
    by_fid = {f.fid: f for f in st.feats}
    st.result = assemble(st.features, st.insights, st.main, st.tech, by_fid, st.ledger, st.idx)
    st.events.append({"type": "assemble", **st.result[4]})
    return {"assembled": True}


def _n(fn, name):
    return node(fn, name=name, rerun_on_resume=True)


_RUNNER: Optional[Runner] = None


def get_runner() -> Runner:
    """Runner·Workflow는 프로세스 싱글턴. 요청마다 세션만 만들고 지운다(스파이크 8: 2.6ms)."""
    global _RUNNER
    if _RUNNER is None:
        workflow = Workflow(
            name="report_v1",
            edges=[(
                "START",
                _n(prep_stage, "prep"),
                (_n(map_stage, "map_stage"), _n(tech_stage, "tech_stage")),
                JoinNode(name="join_map"),
                _n(verify_stage, "verify"),
                (_n(features_stage, "features_stage"), _n(insights_stage, "insights_stage")),
                JoinNode(name="join_detail"),
                _n(main_stage, "main_stage"),
                _n(assemble_stage, "assemble"),
            )],
        )
        app = App(name=APP_NAME, root_agent=workflow, plugins=[rt.UsagePlugin()])
        _RUNNER = Runner(app=app, session_service=InMemorySessionService())
    return _RUNNER


class V1AdkEngine:
    name = "v1_adk"

    async def generate(self, ctx: ReportContext) -> EngineResult:
        runner = get_runner()
        sid = f"v1-{uuid.uuid4().hex[:12]}"
        st = V1State(ctx=ctx, deadline=time.monotonic() + TOTAL_DEADLINE)
        rt.STATES[sid] = st
        svc = runner.session_service
        await svc.create_session(app_name=APP_NAME, user_id="report", session_id=sid)
        try:
            msg = types.Content(role="user", parts=[types.Part(text=f"report:{ctx.project_name}")])
            async for _ in runner.run_async(user_id="report", session_id=sid, new_message=msg):
                pass
        except Exception as e:  # noqa: BLE001 - 워크플로 자체 오류도 폴백 규칙으로 처리
            st.events.append({"type": "workflow_error", "error": rt._cause(e)})
            st.fallback = st.fallback or f"workflow_error:{type(e).__name__}"
        finally:
            await svc.delete_session(app_name=APP_NAME, user_id="report", session_id=sid)
            rt.STATES.pop(sid, None)
            usage = rt.USAGE.pop(sid, [])
            st.events += rt.MODEL_ERRORS.pop(sid, [])

        partial = EngineResult(content={}, techstacks=[], usage=usage, events=st.events)
        if st.error:
            st.error.partial = partial
            raise st.error
        if st.fallback:
            return await self._fallback(ctx, st, usage)
        content, techstacks, tech_refs, fallback_locs, _ = st.result
        return EngineResult(content=content, techstacks=techstacks, usage=usage, events=st.events,
                            tech_refs=tech_refs, fallback_locations=fallback_locs)

    async def _fallback(self, ctx: ReportContext, st: V1State, usage: List[dict]) -> EngineResult:
        remaining = st.remaining()
        if remaining < FALLBACK_MIN_REMAINING:
            st.events.append({"type": "fallback_skipped", "reason": st.fallback, "remaining_s": round(remaining, 1)})
            raise ReportGenerationError("engine_failed", st.fallback, partial=EngineResult({}, [], usage, st.events))
        from app.report.engines.legacy import LegacyEngine

        st.events.append({"type": "fallback", "reason": st.fallback, "remaining_s": round(remaining, 1)})
        logger.warning(f"V1 폴백 → legacy: {st.fallback}")
        res = await LegacyEngine().generate(ctx)
        res.usage = usage + res.usage
        res.events = st.events + res.events
        return res
