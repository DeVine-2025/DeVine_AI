"""LLM 호출 전 가드 (계획 §4.5)."""
from typing import List

from app.report.context import ReportContext
from app.report.errors import ReportGenerationError

LOW_EVIDENCE_MAX_COMMITS = 2
LOW_EVIDENCE_MAX_LINES = 20


def check_guards(ctx: ReportContext) -> List[str]:
    """차단 사유가 있으면 ReportGenerationError, 아니면 참고 플래그 목록을 돌려준다.

    low_evidence 정책(FAILED/축소/그대로)은 미결(Q4)이라 플래그만 남긴다.
    """
    f = ctx.facts
    if f.author_commit_count == 0:
        raise ReportGenerationError("no_author_commits", "작성자 커밋을 찾지 못해 리포트를 만들지 않습니다")
    flags = []
    if f.author_commit_count <= LOW_EVIDENCE_MAX_COMMITS and f.author_added + f.author_deleted < LOW_EVIDENCE_MAX_LINES:
        flags.append("low_evidence")
    return flags
