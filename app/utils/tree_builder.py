import os
from typing import Dict, Any, List

SKIP_DIRS = [
    "node_modules", "vendor", "dist", "build", ".git", "__pycache__",
    ".next", "coverage", ".venv", "venv", "env"
]


def build_directory_tree(dir_path: str, base_path: str, depth: int = 0, max_depth: int = 4) -> Dict[str, Any]:
    tree = {
        "name": os.path.basename(dir_path) or ".",
        "type": "directory",
        "children": []
    }

    if depth >= max_depth:
        tree["children"] = ["..."]
        return tree

    try:
        entries = os.listdir(dir_path)

        dirs = sorted([e for e in entries if os.path.isdir(os.path.join(dir_path, e))])
        files = sorted([e for e in entries if os.path.isfile(os.path.join(dir_path, e))])

        for entry in dirs:
            if entry.startswith(".") or entry in SKIP_DIRS:
                continue

            child_path = os.path.join(dir_path, entry)
            child_tree = build_directory_tree(child_path, base_path, depth + 1, max_depth)
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

            if depth <= 1 or entry.lower() in important_files or ext in code_extensions:
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


def build_project_tree(dir_path: str) -> str:
    tree = build_directory_tree(dir_path, dir_path, 0, 4)

    result = f"{tree['name']}/\n"

    children = tree.get("children", [])
    if isinstance(children, list):
        filtered = [c for c in children if isinstance(c, dict)]
        for i, child in enumerate(filtered):
            is_last = (i == len(filtered) - 1)
            result += tree_to_text(child, "", is_last)

    return result
