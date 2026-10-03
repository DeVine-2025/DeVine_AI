import os
from typing import Dict, Any, List, Iterable, Optional, Set

SKIP_DIRS = [
    "node_modules", "vendor", "dist", "build", ".git", "__pycache__",
    ".next", "coverage", ".venv", "venv", "env"
]


def _focus_sets(focus_paths: Optional[Iterable[str]]) -> tuple:
    files: Set[str] = set()
    dirs: Set[str] = set()
    for p in focus_paths or []:
        files.add(p)
        parts = p.split("/")
        for i in range(1, len(parts)):
            dirs.add("/".join(parts[:i]))
    return files, dirs


def build_directory_tree(
    dir_path: str,
    base_path: str,
    depth: int = 0,
    max_depth: int = 4,
    focus: tuple = (frozenset(), frozenset()),
) -> Dict[str, Any]:
    """디렉터리 트리. focus=(파일 집합, 디렉터리 집합)에 든 경로는 깊이 제한 없이 펼친다."""
    tree = {
        "name": os.path.basename(dir_path) or ".",
        "type": "directory",
        "children": []
    }
    focus_files, focus_dirs = focus
    rel_dir = os.path.relpath(dir_path, base_path).replace(os.sep, "/")
    rel_dir = "" if rel_dir == "." else rel_dir
    beyond_limit = depth >= max_depth

    if beyond_limit and rel_dir not in focus_dirs:
        tree["children"] = ["..."]
        return tree

    try:
        entries = os.listdir(dir_path)

        dirs = sorted([e for e in entries if os.path.isdir(os.path.join(dir_path, e))])
        files = sorted([e for e in entries if os.path.isfile(os.path.join(dir_path, e))])

        def rel(entry: str) -> str:
            return f"{rel_dir}/{entry}" if rel_dir else entry

        for entry in dirs:
            if entry.startswith(".") or entry in SKIP_DIRS:
                continue
            if beyond_limit and rel(entry) not in focus_dirs:
                continue

            child_path = os.path.join(dir_path, entry)
            child_tree = build_directory_tree(child_path, base_path, depth + 1, max_depth, focus)
            tree["children"].append(child_tree)

        code_extensions = [".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rs", ".vue", ".svelte"]
        important_files = [
            "package.json", "requirements.txt", "pyproject.toml",
            "dockerfile", "docker-compose.yml", "readme.md"
        ]

        for entry in files:
            if entry.startswith(".") and entry != ".env.example":
                continue

            ext = os.path.splitext(entry)[1].lower()

            if beyond_limit:
                if rel(entry) in focus_files:
                    tree["children"].append({"name": entry, "type": "file"})
                continue

            if depth <= 1 or entry.lower() in important_files or ext in code_extensions or rel(entry) in focus_files:
                tree["children"].append({
                    "name": entry,
                    "type": "file"
                })

    except PermissionError:
        pass

    return tree


def tree_to_text(tree: Dict[str, Any], prefix: str = "", is_last: bool = True) -> str:
    connector = "└── " if is_last else "├── "
    extension = "    " if is_last else "│   "

    suffix = "/" if tree["type"] == "directory" else ""
    result = f"{prefix}{connector}{tree['name']}{suffix}\n"

    children = tree.get("children", [])
    if isinstance(children, list):
        filtered = [c for c in children if isinstance(c, dict)]
        has_more = any(c == "..." for c in children)

        for i, child in enumerate(filtered):
            child_is_last = (i == len(filtered) - 1) and not has_more
            result += tree_to_text(child, prefix + extension, child_is_last)

        if has_more:
            result += f"{prefix}{extension}└── ...\n"

    return result


def build_project_tree(dir_path: str, focus_paths: Optional[Iterable[str]] = None) -> str:
    """프로젝트 트리 텍스트. focus_paths(작성자가 수정한 파일)는 깊이 4를 넘어도 펼친다."""
    tree = build_directory_tree(dir_path, dir_path, 0, 4, _focus_sets(focus_paths))

    result = f"{tree['name']}/\n"

    children = tree.get("children", [])
    if isinstance(children, list):
        filtered = [c for c in children if isinstance(c, dict)]
        for i, child in enumerate(filtered):
            is_last = (i == len(filtered) - 1)
            result += tree_to_text(child, "", is_last)

    return result
