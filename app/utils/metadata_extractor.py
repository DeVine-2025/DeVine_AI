"""
Metadata Extractor (전체 변경 규모 및 마이그레이션 메타데이터 추출기)

경로 상한선(15~25개)으로 인해 대규모 전사적 리팩토링이나 마이그레이션(100개 이상 파일 수정)의
양적 스케일이 축소되어 보이는 문제를 방지하기 위해 통계 메타데이터를 정밀 집계합니다.
"""

import os
from collections import Counter, defaultdict
from typing import Dict, Any, List


def extract_change_metadata(
    files: Dict[str, Any],
    stats: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    수정된 파일 목록으로부터 디렉토리 분포, 확장자 분포, 마이그레이션 징후 등을 집계합니다.
    """
    total_files = len(files)
    if total_files == 0:
        return {
            "total_modified_files": 0,
            "is_large_scale_refactoring": False,
            "directory_distribution": {},
            "extension_distribution": {},
            "summary_text": "수정된 파일 없음"
        }

    dir_counter = Counter()
    ext_counter = Counter()

    for path in files.keys():
        normalized = path.replace("\\", "/")
        parts = normalized.split("/")
        if len(parts) > 1:
            # 상위 2단계 디렉토리 (예: src/components, app/services)
            top_dir = "/".join(parts[:2])
        else:
            top_dir = "root"
        dir_counter[top_dir] += 1

        ext = os.path.splitext(normalized)[1].lower() or "no-ext"
        ext_counter[ext] += 1

    top_dirs = dir_counter.most_common(5)
    top_exts = ext_counter.most_common(5)

    # 대규모 리팩토링/마이그레이션 판정 (30개 이상 파일 또는 4개 이상의 디렉토리 분산)
    is_large_scale = total_files >= 30 or (total_files >= 20 and len(dir_counter) >= 4)

    # 포맷팅 텍스트 생성
    dir_summary = ", ".join([f"`{d}`: {cnt}개({cnt/total_files*100:.0f}%)" for d, cnt in top_dirs])
    ext_summary = ", ".join([f"`{ext}`: {cnt}개" for ext, cnt in top_exts])

    lines = [
        f"- **총 수정 파일 수**: {total_files}개 (핵심 대표 경로 15~25개 심층 분석)",
        f"- **주요 변경 디렉터리**: {dir_summary}",
        f"- **주요 확장자 분포**: {ext_summary}",
    ]

    if is_large_scale:
        lines.append(
            f"- **마이그레이션/전역 변경 감지**: 대규모 구조 변경 또는 전사적 리팩토링 특성을 보임 "
            f"({len(dir_counter)}개 이상의 디렉토리에 걸친 광범위한 영향력)"
        )

    summary_text = "\n".join(lines)

    return {
        "total_modified_files": total_files,
        "is_large_scale_refactoring": is_large_scale,
        "top_directories": top_dirs,
        "top_extensions": top_exts,
        "directory_distribution": dict(dir_counter),
        "extension_distribution": dict(ext_counter),
        "summary_text": summary_text,
    }
