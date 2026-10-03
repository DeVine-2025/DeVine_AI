import os

from app.utils.tree_builder import build_project_tree


def _touch(root, rel):
    p = os.path.join(root, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w").close()


def test_focus_paths_expand_beyond_depth_limit(tmp_path):
    deep = "src/app/[workspaceId]/@globalModal/(modal)/settings/page.tsx"
    _touch(tmp_path, deep)
    _touch(tmp_path, "src/app/[workspaceId]/@globalModal/(modal)/other/page.tsx")
    _touch(tmp_path, "src/app/[workspaceId]/@globalModal/(modal)/settings/styles.module.css")
    plain = build_project_tree(str(tmp_path))
    assert "settings" not in plain

    tree = build_project_tree(str(tmp_path), focus_paths=[deep, "src/app/[workspaceId]/@globalModal/(modal)/settings/styles.module.css"])
    assert "settings/" in tree and "page.tsx" in tree
    assert "styles.module.css" in tree  # 코드 확장자가 아니어도 작성자 파일은 보인다
    assert "other/" not in tree  # 깊이 제한을 넘는 곳은 작성자 경로만 펼친다


def test_without_focus_is_unchanged(tmp_path):
    _touch(tmp_path, "a/b/c/d/e/f.py")
    assert build_project_tree(str(tmp_path)) == build_project_tree(str(tmp_path), focus_paths=[])
