"""diff 수집에서 뺄 파일 판정 (회의 자료 S1).

lock 파일, SVG·이미지·폰트 같은 에셋, 빌드 생성물은 프롬프트 토큰만 차지하고 기여 판단에 쓸모가 없다.
"""
import os
from typing import Optional

from app.utils.file_reader import SKIP_FILES

MAX_LINE_CHARS = 500

LOCK_FILES = SKIP_FILES | {"bun.lockb", "uv.lock", "go.sum", "gradle.lockfile", "npm-shrinkwrap.json"}
ASSET_EXTS = {
    ".svg", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".bmp", ".avif",
    ".woff", ".woff2", ".ttf", ".otf", ".eot",
    ".mp4", ".mp3", ".wav", ".mov", ".webm", ".pdf", ".zip",
}
CODE_EXTS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".java", ".kt", ".kts", ".go", ".rs",
    ".vue", ".svelte", ".swift", ".dart", ".rb", ".php", ".cs", ".c", ".cpp", ".h", ".css", ".scss",
}
GENERATED_DIRS = {"dist", ".next", "out", "coverage", "node_modules", "__generated__"}
GENERATED_SUFFIXES = (".min.js", ".min.css", ".map", ".class", ".pyc")


def skip_reason(path: str) -> Optional[str]:
    """제외할 파일이면 사유(lockfile/asset/generated), 아니면 None."""
    name = os.path.basename(path)
    ext = os.path.splitext(name)[1].lower()
    parts = path.split("/")[:-1]

    if name in LOCK_FILES:
        return "lockfile"
    if name.endswith(GENERATED_SUFFIXES):
        return "generated"
    if set(parts) & GENERATED_DIRS:
        return "generated"
    if "build" in parts and "src" not in parts[: parts.index("build")]:
        return "generated"
    if ext in ASSET_EXTS:
        return "asset"
    if "assets" in parts and ext not in CODE_EXTS:
        return "asset"
    return None


def truncate_line(line: str) -> str:
    if len(line) <= MAX_LINE_CHARS:
        return line
    return line[:MAX_LINE_CHARS] + "…(잘림)"
