"""V1 장애 주입 테스트 (계획 §9.4). 실제 ADK Workflow를 돌리고 모델만 가짜로 바꾼다.

가짜 모델은 요청의 response_schema(동적 Pydantic 모델)를 보고 스키마에 맞는 최소 응답을 만든다.
시나리오별로 스키마 이름마다 동작 목록(ok / error / badjson / sleep)을 준다.
"""
import asyncio
import json
from typing import Any, AsyncGenerator, Dict, List

import pytest
from google.adk.models import BaseLlm, LlmResponse
from google.genai import types

from app.report.context import build_context
from app.report.engines import adk_runtime as rt
from app.report.engines import v1_adk
from app.report.engines.base import EngineResult
from app.report.errors import ReportGenerationError
from test.test_git_inputs import repo  # noqa: F401


def _sample(schema: dict, defs: dict) -> Any:
    if "$ref" in schema:
        return _sample(defs[schema["$ref"].split("/")[-1]], defs)
    if "enum" in schema:
        return schema["enum"][0]
    if "const" in schema:
        return schema["const"]
    if "anyOf" in schema:
        return _sample(schema["anyOf"][0], defs)
    t = schema.get("type")
    if t == "object":
        return {k: _sample(v, defs) for k, v in schema.get("properties", {}).items()}
    if t == "array":
        return [_sample(schema["items"], defs)]
    if t == "integer":
        return 1
    return "값"


class FakeControl:
    """시나리오 설정과 호출 수. pydantic 필드로 두면 인스턴스마다 기본값이 복사되므로 모듈 객체에 둔다."""

    plan: Dict[str, List[str]] = {}
    calls: Dict[str, int] = {}


class FakeLlm(BaseLlm):
    model: str = "fake"

    async def generate_content_async(self, llm_request, stream: bool = False) -> AsyncGenerator[LlmResponse, None]:
        schema_cls = llm_request.config.response_schema
        name = schema_cls.__name__
        n = FakeControl.calls.get(name, 0)
        FakeControl.calls[name] = n + 1
        steps = FakeControl.plan.get(name, [])
        action = steps[n] if n < len(steps) else "ok"
        if action == "error":
            raise RuntimeError(f"injected 503 for {name}")
        if action.startswith("sleep"):
            await asyncio.sleep(float(action.split(":")[1]))
        js = schema_cls.model_json_schema()
        text = "{not json" if action == "badjson" else json.dumps(_sample(js, js.get("$defs", {})), ensure_ascii=False)
        yield LlmResponse(
            content=types.Content(role="model", parts=[types.Part(text=text)]),
            usage_metadata=types.GenerateContentResponseUsageMetadata(prompt_token_count=10, candidates_token_count=5),
        )


@pytest.fixture
def fake(monkeypatch):
    FakeControl.plan, FakeControl.calls = {}, {}
    monkeypatch.setattr(rt, "make_model", lambda: FakeLlm())
    fallback_calls = []

    async def fake_legacy(self, ctx):
        fallback_calls.append(1)
        return EngineResult(content={"legacy": True}, techstacks=[], usage=[{"node": "single"}])

    from app.report.engines import legacy
    monkeypatch.setattr(legacy.LegacyEngine, "generate", fake_legacy)
    return FakeControl, fallback_calls


def _ctx(repo_path):
    return build_context(repo_path, "https://github.com/o/myrepo", "alice", ["alice@x.com"], ["TYPESCRIPT", "BACKEND"])


def _types(res):
    return [e["type"] for e in res.events]


@pytest.mark.asyncio
async def test_happy_path(repo, fake):  # noqa: F811
    llm, fallback = fake
    res = await v1_adk.V1AdkEngine().generate(_ctx(repo))
    assert not fallback
    assert res.content["detail"]["implementedFeatures"][0]["features"][0]["codeLocation"]
    assert {u["node"] for u in res.usage} >= {"map_1", "tech", "features", "insights", "main"}
    assert "fallback" not in _types(res)


@pytest.mark.asyncio
async def test_node_error_once_recovers_only_that_node(repo, fake):  # noqa: F811
    llm, fallback = fake
    llm.plan = {"FeaturesSection": ["error"]}
    res = await v1_adk.V1AdkEngine().generate(_ctx(repo))
    assert not fallback
    assert {"retry", "recovered"} <= set(_types(res))
    assert llm.calls["FeaturesSection"] == 2 and llm.calls["InsightsSection"] == 1  # 다른 노드는 다시 부르지 않는다


@pytest.mark.asyncio
async def test_bad_json_once_regenerates(repo, fake):  # noqa: F811
    llm, fallback = fake
    llm.plan = {"InsightsSection": ["badjson"]}
    res = await v1_adk.V1AdkEngine().generate(_ctx(repo))
    assert not fallback and "recovered" in _types(res)


@pytest.mark.asyncio
async def test_section_fails_twice_falls_back_to_legacy(repo, fake):  # noqa: F811
    llm, fallback = fake
    llm.plan = {"FeaturesSection": ["error", "error"]}
    res = await v1_adk.V1AdkEngine().generate(_ctx(repo))
    assert fallback == [1]
    assert res.content == {"legacy": True}
    assert "fallback" in _types(res)
    assert "MainSection" not in llm.calls  # 실패 후 뒤 단계는 돌지 않는다


@pytest.mark.asyncio
async def test_node_timeout_then_recover(repo, fake, monkeypatch):  # noqa: F811
    llm, fallback = fake
    monkeypatch.setitem(v1_adk.TIMEOUTS, "main", 0.5)
    llm.plan = {"MainSection": ["sleep:2"]}
    res = await v1_adk.V1AdkEngine().generate(_ctx(repo))
    retry = next(e for e in res.events if e["type"] == "retry")
    assert retry["node"] == "main" and retry["error"] == "timeout"
    assert "recovered" in _types(res) and not fallback


@pytest.mark.asyncio
async def test_map_failure_majority_falls_back(repo, fake):  # noqa: F811
    llm, fallback = fake
    llm.plan = {"EvidenceCard": ["error", "error"]}
    res = await v1_adk.V1AdkEngine().generate(_ctx(repo))
    assert fallback == [1]
    assert any(e["type"] == "fallback" and e["reason"].startswith("map_failed") for e in res.events)


@pytest.mark.asyncio
async def test_tech_failure_degrades_without_fallback(repo, fake):  # noqa: F811
    llm, fallback = fake
    llm.plan = {"TechSection": ["error", "error"]}
    res = await v1_adk.V1AdkEngine().generate(_ctx(repo))
    assert not fallback and res.techstacks == [] and res.tech_refs is None
    assert "tech_degraded" in _types(res)


@pytest.mark.asyncio
async def test_no_time_left_fails_instead_of_fallback(repo, fake, monkeypatch):  # noqa: F811
    llm, fallback = fake
    monkeypatch.setattr(v1_adk, "TOTAL_DEADLINE", 30.0)  # 남은 시간 < 60초 → 폴백하지 않고 실패
    llm.plan = {"FeaturesSection": ["error", "error"]}
    with pytest.raises(ReportGenerationError) as e:
        await v1_adk.V1AdkEngine().generate(_ctx(repo))
    assert e.value.reason == "engine_failed" and not fallback
    assert e.value.partial.events
