"""
Diff & Tree Budgeter v3 (상한선, 비례 절단, AST 구조 압축 및 인프라 분리 모듈)
참고: C:\\git\\umc11th\\workbook_backend\\src\\domain\\notion\\parser.ts (DEFAULT_MAX_CONTEXT_CHARS 비례 절단 패턴)

v3 고도화 기능:
1) AST & Code Outliner 연동: 단일 거대 파일(1,000줄 이상)에서 함수/클래스 시그니처 우선 보존 및 본문 압축
2) Dedicated Infra Budget: 비즈니스 로직 diff와 인프라/설정 diff를 분리하여 인프라 기여 독립 보장
3) 디렉토리 트리 상한선 보존
"""

import logging
from typing import Dict, Any, Tuple, List, Optional

from app.utils.code_outliner import compress_diff_block
from app.utils.infra_detector import is_infra_file, partition_file_changes

logger = logging.getLogger(__name__)

DEFAULT_MAX_BUSINESS_DIFF_CHARS = 60_000   # 비즈니스 로직 diff 상한
DEFAULT_MAX_INFRA_DIFF_CHARS = 25_000      # 인프라/설정 diff 전용 독립 예산
DEFAULT_MAX_DIFF_CHARS = 80_000            # 레거시 호환 총 상한
DEFAULT_MAX_TREE_CHARS = 35_000            # 디렉토리 트리 상한


def _format_and_budget_file_group(
    files: Dict[str, Any],
    max_total_chars: int,
    max_files: int = 35,
    max_commits_per_file: int = 8,
    min_chars_per_file: int = 350,
    per_file_collapse_threshold: int = 5000,
) -> Tuple[str, bool]:
    """단일 그룹(비즈니스 또는 인프라)의 파일들을 AST 압축 및 비례 절단"""
    if not files:
        return "", False

    # 커밋 수 및 라인 변경량 기준 정렬
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

        raw_block_text = "".join(block_lines)

        # 거대 파일의 경우 AST / Code Outliner로 구조적 압축 선행 적용
        if len(raw_block_text) > per_file_collapse_threshold:
            compressed_block = compress_diff_block(
                file_path=path,
                diff_text=raw_block_text,
                target_max_chars=per_file_collapse_threshold,
            )
            file_blocks.append((path, compressed_block))
        else:
            file_blocks.append((path, raw_block_text))

    total_chars = sum(len(b[1]) for b in file_blocks)

    if total_chars <= max_total_chars:
        return "".join(b[1] for b in file_blocks), False

    # 비례 절단 (Proportional Truncation) 적용
    ratio = max_total_chars / total_chars
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
    return result_text, True


def budget_file_changes_v3(
    files: Dict[str, Any],
    max_business_chars: int = DEFAULT_MAX_BUSINESS_DIFF_CHARS,
    max_infra_chars: int = DEFAULT_MAX_INFRA_DIFF_CHARS,
) -> Tuple[str, str, bool]:
    """
    v3 이원화 Diff 예산 배분 함수.
    비즈니스 로직과 인프라/설정 파일을 분리하여 독립 예산을 부여하고 AST 압축을 적용합니다.

    Returns:
        (business_diff, infra_diff, is_truncated)
    """
    business_files, infra_files = partition_file_changes(files)
    logger.info(
        f"[DiffBudgeterV3] 파일 이원화 분리: 비즈니스 로직 {len(business_files)}개, 인프라/설정 {len(infra_files)}개"
    )

    business_diff, b_trunc = _format_and_budget_file_group(
        business_files,
        max_total_chars=max_business_chars,
        max_files=35,
        per_file_collapse_threshold=6000
    )

    infra_diff, i_trunc = _format_and_budget_file_group(
        infra_files,
        max_total_chars=max_infra_chars,
        max_files=20,
        per_file_collapse_threshold=4500
    )

    is_truncated = b_trunc or i_trunc
    logger.info(
        f"[DiffBudgeterV3] 예산 배정 완료 -> 비즈니스: {len(business_diff):,}자, 인프라: {len(infra_diff):,}자"
    )
    return business_diff, infra_diff, is_truncated


def budget_file_changes(
    files: Dict[str, Any],
    max_total_chars: int = DEFAULT_MAX_DIFF_CHARS,
    max_files: int = 45,
    max_commits_per_file: int = 8,
    min_chars_per_file: int = 350,
) -> Tuple[str, bool]:
    """기존 파이프라인 호환용 단일 통합 diff 반환 함수"""
    b_diff, i_diff, trunc = budget_file_changes_v3(
        files,
        max_business_chars=int(max_total_chars * 0.7),
        max_infra_chars=int(max_total_chars * 0.3)
    )
    combined = b_diff
    if i_diff:
        combined += "\n\n=== [인프라 및 환경 설정 파일 변경 내역] ===\n" + i_diff
    return combined, trunc


def budget_tree_structure(
    tree_text: str,
    max_chars: int = DEFAULT_MAX_TREE_CHARS
) -> Tuple[str, bool]:
    """디렉토리 트리 문자열이 상한을 넘으면 상위 핵심 구조 위주로 절단"""
    if len(tree_text) <= max_chars:
        return tree_text, False

    lines = tree_text.splitlines()
    truncated_lines = []
    current_chars = 0

    for line in lines:
        if current_chars + len(line) + 1 > max_chars - 300:
            truncated_lines.append("... (하위 디렉토리 생략 - 디렉토리 트리 상한 도달)")
            break
        truncated_lines.append(line)
        current_chars += len(line) + 1

    return "\n".join(truncated_lines), True
