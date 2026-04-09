import os
import subprocess
from typing import List, Dict

from binaryornot.check import is_binary

SKIP_DIRS = [
    "node_modules", "vendor", "dist", "build", ".git", "__pycache__",
    ".next", "coverage", ".venv", "venv", "env", ".idea", ".vscode"
]

# 자동생성 락파일 (내용이 의미 없는 파일)
SKIP_FILES = {
    # 패키지 락파일
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "Pipfile.lock", "poetry.lock", "composer.lock",
    "Gemfile.lock", "Cargo.lock", "mix.lock",
    # OS 메타데이터
    ".DS_Store", "Thumbs.db", "desktop.ini",
}


def get_all_files(dir_path: str) -> List[str]:
    files = []

    for root, dirs, filenames in os.walk(dir_path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]

        for filename in filenames:
            if filename in SKIP_FILES or filename.startswith("."):
                continue

            rel_path = os.path.relpath(os.path.join(root, filename), dir_path)
            files.append(rel_path)

    return files


def get_git_tracked_files(dir_path: str) -> List[str]:
    """git ls-files로 추적 중인 파일만 반환. git 환경이 아니면 get_all_files로 fallback."""
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=dir_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
        if result.returncode == 0 and result.stdout.strip():
            return [f for f in result.stdout.strip().split("\n") if f]
    except Exception:
        pass
    return get_all_files(dir_path)


def get_code_files(dir_path: str) -> List[str]:
    """git 추적 파일 기준으로 바이너리/자동생성 파일을 제외한 작업 파일 목록 반환."""
    all_files = get_git_tracked_files(dir_path)

    code_files = []
    for file in all_files:
        filename = os.path.basename(file)

        # 락파일/OS 메타 스킵
        if filename in SKIP_FILES:
            continue

        # 미니파이된 파일 스킵 (예: bundle.min.js, app.min.css)
        if ".min." in filename:
            continue

        # 실제 파일 내용 기반 바이너리 판별
        abs_path = os.path.join(dir_path, file)
        try:
            if is_binary(abs_path):
                continue
        except Exception:
            continue

        code_files.append(file)

    return code_files


def count_lines(file_path: str) -> int:
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


def count_test_files(dir_path: str) -> int:
    all_files = get_all_files(dir_path)
    test_count = 0

    test_patterns = [
        "test_", "_test.", ".test.", ".spec.",
        "tests/", "test/", "__tests__/", "spec/"
    ]

    for file in all_files:
        file_lower = file.lower()
        for pattern in test_patterns:
            if pattern in file_lower:
                test_count += 1
                break

    return test_count
