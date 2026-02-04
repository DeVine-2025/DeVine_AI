from typing import Any


def extract_embedding_text(report: dict[str, Any]) -> str:
    """
    리포트 JSON에서 임베딩용 요약 텍스트를 추출합니다.

    추출 필드:
    - overview.summary: 프로젝트 요약
    - overview.mainTech: 주요 기술
    - projectInfo.techStack: 기술 스택 목록
    - keyImplementations[].title: 핵심 구현 제목들
    """
    parts: list[str] = []

    # overview.summary
    overview = report.get("overview", {})
    if summary := overview.get("summary"):
        parts.append(summary)

    # overview.mainTech
    if main_tech := overview.get("mainTech"):
        parts.append(main_tech)

    # projectInfo.techStack
    project_info = report.get("projectInfo", {})
    if tech_stack := project_info.get("techStack"):
        if isinstance(tech_stack, list):
            parts.append(", ".join(tech_stack))

    # keyImplementations[].title
    key_implementations = report.get("keyImplementations", [])
    for impl in key_implementations:
        if title := impl.get("title"):
            parts.append(title)

    return "\n".join(parts)
