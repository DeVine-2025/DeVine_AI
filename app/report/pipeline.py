"""리포트 생성 파이프라인: 입력 수집 → 가드 → 엔진 → 후처리 (계획 §4.1).

analyzer(운영 경로)와 eval 하네스가 같은 함수를 호출한다.
"""
import asyncio
import logging
import time
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional

from app.configs.settings import settings
from app.report.context import build_context
from app.report.engines import EngineResult, get_engine
from app.report.guards import check_guards
from app.report.postprocess import postprocess

logger = logging.getLogger(__name__)


@dataclass
class ReportOutcome:
    engine: str
    content: Optional[dict] = None  # 후처리·계약 검증을 통과한 최종 dict(백엔드로 보냄)
    techstacks: List[str] = field(default_factory=list)
    raw_content: Optional[dict] = None  # 엔진 출력(후처리 전). 평가용
    raw_techstacks: List[str] = field(default_factory=list)
    corrections: Dict[str, int] = field(default_factory=dict)
    usage: List[dict] = field(default_factory=list)
    events: List[dict] = field(default_factory=list)
    timings: Dict[str, int] = field(default_factory=dict)
    flags: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _ms(t0: float) -> int:
    return int((time.perf_counter() - t0) * 1000)


async def generate_report(
    dir_path: str,
    repo_url: str,
    author_name: str,
    author_emails: List[str],
    available_techstacks: Optional[List[str]] = None,
    engine_name: Optional[str] = None,
    log_prefix: str = "",
) -> ReportOutcome:
    engine = get_engine(engine_name or settings.report_engine)
    outcome = ReportOutcome(engine=engine.name)
    try:
        t0 = time.perf_counter()
        ctx = await asyncio.to_thread(build_context, dir_path, repo_url, author_name, author_emails, available_techstacks)
        outcome.timings["context_ms"] = _ms(t0)
        outcome.flags = check_guards(ctx)

        t0 = time.perf_counter()
        result: EngineResult = await engine.generate(ctx)
        outcome.timings["engine_ms"] = _ms(t0)
        outcome.raw_content, outcome.raw_techstacks = result.content, list(result.techstacks)
        outcome.usage, outcome.events = result.usage, result.events

        t0 = time.perf_counter()
        pp = postprocess(result.content, result.techstacks, ctx, result.tech_refs, result.fallback_locations)
        outcome.timings["postprocess_ms"] = _ms(t0)
        outcome.content, outcome.techstacks, outcome.corrections = pp.content.to_legacy_dict(), pp.techstacks, pp.corrections
        logger.info(
            f"{log_prefix} 리포트 생성 완료 engine={engine.name} timings={outcome.timings} "
            f"calls={len(outcome.usage)} corrections={outcome.corrections} flags={outcome.flags}"
        )
        return outcome
    except Exception as e:
        partial = getattr(e, "partial", None)
        if isinstance(partial, EngineResult):
            outcome.usage, outcome.events = partial.usage, partial.events
        e.outcome = outcome
        raise
