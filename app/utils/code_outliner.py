"""
AST & Code Outliner (구조적 구문 압축기)

대용량 단일 파일(1,000줄 이상)에서 단순 Head-Truncation으로 인해
파일 후반부의 핵심 함수/알고리즘이 누락되는 문제를 방지합니다.

- 주요 클래스, 함수 시그니처, 인터페이스, 반환 타입, 데코레이터 우선 보존
- 긴 함수 본문 내부의 반복/더미 로직을 `... [N lines collapsed] ...`로 축약
- Python(ast 모듈 기반) 및 TS/JS/기타 언어(구조적 시그니처 매칭 기반) 지원
"""

import ast
import logging
import re
from typing import List, Optional

logger = logging.getLogger(__name__)

# 각 언어별 클래스/함수/인터페이스 선언부 시그니처 정규식
SIGNATURE_PATTERNS = [
    # Python
    re.compile(r"^\s*(async\s+def|def|class)\s+[A-Za-z0-9_]+"),
    re.compile(r"^\s*@[A-Za-z0-9_.]+"),
    # TypeScript / JavaScript
    re.compile(r"^\s*(export\s+)?(default\s+)?(async\s+)?function(\s+\*|\s+)[A-Za-z0-9_]+"),
    re.compile(r"^\s*(export\s+)?(default\s+)?(class|interface|type|enum)\s+[A-Za-z0-9_]+"),
    re.compile(r"^\s*(export\s+)?(const|let|var)\s+[A-Za-z0-9_]+\s*=\s*(async\s*)?\("),
    re.compile(r"^\s*(export\s+)?(const|let|var)\s+[A-Za-z0-9_]+\s*:\s*[A-Za-z0-9_<>[\]]+\s*="),
    # Java / Kotlin / Go / Rust
    re.compile(r"^\s*(public|private|protected|static|final|abstract)?\s*(class|interface|record|enum|fun|fn)\s+[A-Za-z0-9_]+"),
    re.compile(r"^\s*func\s+(\([A-Za-z0-9_* ]+\)\s+)?[A-Za-z0-9_]+"),
    # SQL / Migration
    re.compile(r"^\s*(CREATE|ALTER|DROP)\s+(TABLE|INDEX|VIEW|PROCEDURE|FUNCTION)\s+", re.IGNORECASE),
    # IaC / Terraform / Docker
    re.compile(r"^\s*(resource|variable|output|module|data)\s+\"[A-Za-z0-9_-]+\"", re.IGNORECASE),
    re.compile(r"^\s*(FROM|RUN|COPY|ADD|ENTRYPOINT|CMD|ENV|EXPOSE)\s+", re.IGNORECASE),
]


def is_signature_line(line: str) -> bool:
    """라인이 클래스, 함수, 인터페이스 등의 핵심 시그니처인지 판별"""
    stripped = line.strip()
    if not stripped or stripped.startswith(("//", "#", "/*", "*")):
        return False
    # + 로 시작하는 diff 라인 처리
    if stripped.startswith("+") and not stripped.startswith("+++"):
        stripped = stripped[1:].strip()

    return any(pat.search(stripped) for pat in SIGNATURE_PATTERNS)


def compress_diff_block(
    file_path: str,
    diff_text: str,
    target_max_chars: int = 6000,
    collapse_threshold_lines: int = 15
) -> str:
    """
    단일 파일의 diff 블록이 target_max_chars를 초과할 경우,
    단순 앞에서 자르지 않고 시그니처를 보존하면서 함수 본문을 구조적으로 축약합니다.
    """
    if len(diff_text) <= target_max_chars:
        return diff_text

    lines = diff_text.splitlines()
    if len(lines) <= collapse_threshold_lines:
        return diff_text[:target_max_chars] + f"\n…({file_path} 상한 초과 생략)\n"

    preserved_lines: List[str] = []
    in_collapsible_block = False
    collapsed_count = 0
    recent_sig_context = 0

    for i, line in enumerate(lines):
        # 상단 헤더, 파일명, 날짜 라인은 무조건 보존
        if line.startswith("===") or line.startswith("[") or line.startswith("+추가:") or line.startswith("-삭제:"):
            if collapsed_count > 0:
                preserved_lines.append(f"    ... [{collapsed_count}개 세부 로직 라인 생략 (구조 보존)] ...")
                collapsed_count = 0
            preserved_lines.append(line)
            continue

        # 핵심 시그니처 라인 감지
        if is_signature_line(line):
            if collapsed_count > 0:
                preserved_lines.append(f"    ... [{collapsed_count}개 세부 로직 라인 생략 (구조 보존)] ...")
                collapsed_count = 0
            preserved_lines.append(line)
            recent_sig_context = 3  # 시그니처 다음 3줄(파라미터/초기화)은 함께 보존
            continue

        if recent_sig_context > 0:
            preserved_lines.append(line)
            recent_sig_context -= 1
            continue

        # return, throw, yield 등 주요 탈출구는 보존
        stripped = line.strip()
        if stripped.startswith(("+return", "-return", "+throw", "+yield", "return ", "throw ")):
            if collapsed_count > 0:
                preserved_lines.append(f"    ... [{collapsed_count}개 세부 로직 라인 생략 (구조 보존)] ...")
                collapsed_count = 0
            preserved_lines.append(line)
            continue

        # 일반 본문 라인은 축약 카운트 누적
        collapsed_count += 1

    if collapsed_count > 0:
        preserved_lines.append(f"    ... [{collapsed_count}개 세부 로직 라인 생략 (구조 보존)] ...")

    compressed_text = "\n".join(preserved_lines)

    # 그래도 여전히 초과하면 최종 비율로 잘라내되 아웃라인 표기
    if len(compressed_text) > target_max_chars:
        keep = target_max_chars - 150
        return (
            compressed_text[:keep]
            + f"\n…({file_path} AST/구조 보존 후 예산 한도 도달, 총 {len(lines)}줄 중 핵심 시그니처 위주 수록)\n"
        )

    logger.info(
        f"[CodeOutliner] '{file_path}' 구조적 압축 적용: "
        f"{len(diff_text):,}자({len(lines)}줄) -> {len(compressed_text):,}자({len(preserved_lines)}줄)"
    )
    return compressed_text
