import pytest

from app.utils.diff_filter import MAX_LINE_CHARS, skip_reason, truncate_line


@pytest.mark.parametrize("path,reason", [
    ("pnpm-lock.yaml", "lockfile"),
    ("apps/web/package-lock.json", "lockfile"),
    ("public/icons/logo.svg", "asset"),
    ("src/assets/images/bg.png", "asset"),
    ("public/fonts/Pretendard.woff2", "asset"),
    ("dist/index.js", "generated"),
    ("static/js/app.min.js", "generated"),
    ("build/classes/Main.class", "generated"),
    ("src/main.js.map", "generated"),
])
def test_skipped_paths(path, reason):
    assert skip_reason(path) == reason


@pytest.mark.parametrize("path", [
    "src/assets/icons/index.ts",
    "src/components/Button.tsx",
    "app/services/git_service.py",
    "build.gradle",
    "package.json",
    "src/main/java/com/x/build/BuildService.java",
])
def test_kept_paths(path):
    assert skip_reason(path) is None


def test_truncate_line():
    long = "a" * (MAX_LINE_CHARS + 100)
    out = truncate_line(long)
    assert len(out) <= MAX_LINE_CHARS + 20
    assert out.endswith("…(잘림)")
    assert truncate_line("short") == "short"
