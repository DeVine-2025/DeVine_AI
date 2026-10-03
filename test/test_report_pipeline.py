import pytest

from app.report import pipeline
from app.report.engines import EngineResult
from app.report.errors import ReportGenerationError
from test.test_git_inputs import repo  # noqa: F401  (임시 git 레포 fixture)
from test.test_report_postprocess import _raw


class FakeEngine:
    name = "fake"

    def __init__(self):
        self.calls = 0

    async def generate(self, ctx):
        self.calls += 1
        raw = _raw()
        raw["detail"]["implementedFeatures"][0]["features"][0]["codeLocation"] = ["src/old.ts", "ghost.ts"]
        return EngineResult(content=raw, techstacks=["TYPESCRIPT", "BACKEND"], usage=[{"node": "x"}])


@pytest.fixture
def fake(monkeypatch):
    engine = FakeEngine()
    monkeypatch.setattr(pipeline, "get_engine", lambda name: engine)
    return engine


@pytest.mark.asyncio
async def test_pipeline_runs_context_engine_postprocess(repo, fake):  # noqa: F811
    out = await pipeline.generate_report(repo, "https://github.com/o/myrepo", "alice", ["alice@x.com"], ["BACKEND", "TYPESCRIPT"])
    assert fake.calls == 1
    assert out.techstacks == ["TYPESCRIPT"]
    assert out.content["detail"]["reportTitle"] == "myrepo"
    feat = out.content["detail"]["implementedFeatures"][0]["features"][0]
    assert feat["codeLocation"] == ["src/lib/renamed.ts"]
    assert out.corrections["path_renamed"] == 1 and out.corrections["path_dropped"] >= 1
    assert set(out.timings) == {"context_ms", "engine_ms", "postprocess_ms"}
    assert out.raw_content["detail"]["implementedFeatures"][0]["features"][0]["codeLocation"] == ["src/old.ts", "ghost.ts"]


@pytest.mark.asyncio
async def test_pipeline_blocks_zero_commit_author_before_llm(repo, fake):  # noqa: F811
    with pytest.raises(ReportGenerationError) as e:
        await pipeline.generate_report(repo, "https://github.com/o/myrepo", "ghost", ["ghost@none"], [])
    assert e.value.reason == "no_author_commits"
    assert fake.calls == 0
    assert e.value.outcome.timings["context_ms"] >= 0
