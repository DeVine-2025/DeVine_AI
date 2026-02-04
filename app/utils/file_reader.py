import os
from typing import List, Dict

CODE_EXTENSIONS = [
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".kt", ".swift",
    ".go", ".rs", ".rb", ".php", ".cs", ".cpp", ".c", ".h",
    ".vue", ".svelte", ".html", ".css", ".scss", ".sass", ".less"
]

SKIP_DIRS = [
    "node_modules", "vendor", "dist", "build", ".git", "__pycache__",
    ".next", "coverage", ".venv", "venv", "env", ".idea", ".vscode"
]

SKIP_FILES = [
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    ".DS_Store", "Thumbs.db"
]


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


def get_code_files(dir_path: str) -> List[str]:
    all_files = get_all_files(dir_path)

    code_files = []
    for file in all_files:
        ext = os.path.splitext(file)[1].lower()
        if ext in CODE_EXTENSIONS:
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
