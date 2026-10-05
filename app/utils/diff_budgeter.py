"""
Diff & Tree Budgeter (상한선 및 비례 절단 모듈)
참고: C:\\git\\umc11th\\workbook_backend\\src\\domain\\notion\\parser.ts (DEFAULT_MAX_CONTEXT_CHARS 비례 절단 패턴)

대용량 저장소의 Git Diff와 디렉토리 트리가 프롬프트 전체를 잠식하여
1) 콜드 스타트 지연(80~110초), 2) 비용 폭증, 3) 컨텍스트 오염을 유발하는 문제를 방지합니다.
"""

import logging
from typing import Dict, Any, Tuple, List

logger = logging.getLogger(__name__)

DEFAULT_MAX_DIFF_CHARS = 80_000   # 약 20,000 ~ 25,000 토큰 상한
DEFAULT_MAX_TREE_CHARS = 35_000   # 약 8,000 ~ 10,000 토큰 상한


def budget_file_changes(
    files: Dict[str, Any],
    max_total_chars: int = DEFAULT_MAX_DIFF_CHARS,
    max_files: int = 45,
    max_commits_per_file: int = 8,
    min_chars_per_file: int = 350,
) -> Tuple[str, bool]:
    """
    각 파일의 변경 분량을 총량 상한(max_total_chars) 내로 비례 절단(Proportional Truncation)합니다.
    특정 대용량 파일이 전체 예산을 독점하지 않고, 모든 수정 파일의 핵심 변경점이 균형 있게 포함됩니다.
    
    Returns:
        (조립된 diff 문자열, 절단 발생 여부)
    """
    if not files:
        return "", False

    # 1. 파일 우선순위 정렬: 커밋 횟수 및 추가/삭제 라인 수 기준
    sorted_files = sorted(
        files.items(),
        key=lambda item: (
            item[1].get("commits", 0),
            sum(len(c.get("added", [])) + len(c.get("deleted", [])) for c in item[1].get("changes", []))
        ),
        reverse=True
    )[:max_files]

    file_blocks: List[Tuple[str, str]] = []

    for path, data in sorted_files:
        block_lines = [f"\n=== {path} (커밋 {data.get('commits', 1)}회) ===\n"]

        changes = data.get("changes", [])[:max_commits_per_file]
        for change in changes:
            block_lines.append(f"[{change.get('date', '')}] {change.get('message', '')}\n")

            added = change.get("added", [])
            if added:
                block_lines.append("+추가:\n" + "\n".join(added) + "\n")

            deleted = change.get("deleted", [])
            if deleted:
                block_lines.append("-삭제:\n" + "\n".join(deleted) + "\n")

        file_blocks.append((path, "".join(block_lines)))

    total_chars = sum(len(b[1]) for b in file_blocks)
    logger.info(f"[DiffBudgeter] 원본 diff 글자수: {total_chars:,}자 ({len(file_blocks)}개 파일)")

    if total_chars <= max_total_chars:
        return "".join(b[1] for b in file_blocks), False

    # 2. 비례 절단 (Proportional Truncation) 적용
    # ratio에 따라 각 파일의 블록 길이를 균등하게 축소
    ratio = max_total_chars / total_chars
    logger.info(f"[DiffBudgeter] 상한선({max_total_chars:,}자) 초과 감지 -> 비례 축소 계수 {ratio:.3f} 적용")

    budgeted_blocks: List[str] = []
    for path, block in file_blocks:
        keep_length = max(min_chars_per_file, int(len(block) * ratio))
        if len(block) > keep_length:
            truncated_block = (
                f"{block[:keep_length]}\n"
                f"…({path} 변경 분량 상한으로 이하 생략)\n"
            )
            budgeted_blocks.append(truncated_block)
        else:
            budgeted_blocks.append(block)

    result_text = "".join(budgeted_blocks)
    logger.info(f"[DiffBudgeter] 비례 절단 완료: {len(result_text):,}자 (감소율: {(1 - len(result_text)/total_chars)*100:.1f}%)")
    return result_text, True


def budget_tree_structure(
    tree_text: str,
    max_chars: int = DEFAULT_MAX_TREE_CHARS
) -> Tuple[str, bool]:
    """
    디렉토리 트리 문자열이 상한을 넘으면 상위 핵심 구조 위주로 절단합니다.
    """
    if len(tree_text) <= max_chars:
        return tree_text, False

    lines = tree_text.splitlines(keepends=True)
    accumulated: List[str] = []
    current_length = 0

    for line in lines:
        if current_length + len(line) > max_chars - 100:
            accumulated.append("\n…(디렉토리 구조 상한 초과로 하위 경로 생략)\n")
            break
        accumulated.append(line)
        current_length += len(line)

    result = "".join(accumulated)
    logger.info(f"[DiffBudgeter] 트리 상한 절단: {len(tree_text):,}자 -> {len(result):,}자")
    return result, True
