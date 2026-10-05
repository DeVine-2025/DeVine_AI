from eval.metrics import _norm_path


def test_norm_path_keeps_dotfiles_and_route_groups():
    assert _norm_path(".gitignore") == ".gitignore"
    assert _norm_path("./src/a.ts") == "src/a.ts"
    assert _norm_path("src/app/(assistant)/[id]/page.tsx") == "src/app/(assistant)/[id]/page.tsx"
    assert _norm_path("src/app/@modal/(.)settings/layout.tsx") == "src/app/@modal/(.)settings/layout.tsx"


def test_norm_path_strips_line_suffix_and_notes():
    assert _norm_path("`app/main.py:12`") == "app/main.py"
    assert _norm_path("app/main.py#L10") == "app/main.py"
    assert _norm_path("app/main.py (라우터)") == "app/main.py"
