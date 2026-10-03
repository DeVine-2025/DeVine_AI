"""0-5 입력 수정: diff 필터, shortlog, 타 기여자 상세, 이름 변경 맵 (임시 git 레포로 검증)."""
import os
import subprocess

import pytest

from app.services.git_service import (
    analyze_contributor_changes,
    get_all_contributors_summary,
    get_commit_diff,
    get_other_contributor_details,
    get_rename_map,
)


def _git(repo, *args, env=None):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, env=env)


def _commit(repo, name, email, msg, files: dict, delete=()):
    for path, text in files.items():
        full = os.path.join(repo, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as f:
            f.write(text)
    for path in delete:
        os.remove(os.path.join(repo, path))
    env = {**os.environ, "GIT_AUTHOR_NAME": name, "GIT_AUTHOR_EMAIL": email,
           "GIT_COMMITTER_NAME": name, "GIT_COMMITTER_EMAIL": email}
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", msg, env=env)


@pytest.fixture
def repo(tmp_path):
    r = str(tmp_path)
    _git(r, "init", "-q", "-b", "main")
    _commit(r, "alice", "alice@x.com", "init", {
        "src/app.ts": "export const a = 1;\n" + "x" * 900 + "\n",
        "pnpm-lock.yaml": "lock\n" * 50,
        "public/logo.svg": "<svg>" + "M0 0" * 100 + "</svg>\n",
        "src/old.ts": "old\n",
    })
    _commit(r, "bob", "bob@y.com", "feat: bob api", {"server/api/user.ts": "u\n", "server/api/post.ts": "p\n"})
    _commit(r, "bob", "bob@y.com", "feat: bob db", {"server/db/conn.ts": "c\n"})
    os.makedirs(os.path.join(r, "src/lib"), exist_ok=True)
    _git(r, "mv", "src/old.ts", "src/lib/renamed.ts")
    _commit(r, "alice", "alice@x.com", "refactor: move", {"src/app.ts": "export const a = 2;\n"})
    return r


def test_commit_diff_filters_lock_and_svg_and_truncates(repo):
    first = subprocess.run(["git", "rev-list", "--max-parents=0", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()
    diff = get_commit_diff(repo, first)
    paths = [f["path"] for f in diff["files"]]
    assert "src/app.ts" in paths
    assert "pnpm-lock.yaml" not in paths and "public/logo.svg" not in paths
    assert diff["excluded"] == {"pnpm-lock.yaml": "lockfile", "public/logo.svg": "asset"}
    long_line = [l for l in next(f for f in diff["files"] if f["path"] == "src/app.ts")["added"] if l.startswith("x")][0]
    assert long_line.endswith("…(잘림)")
    assert diff["stats"]["added"] == 3  # app.ts 2줄 + old.ts 1줄, lock/svg 제외


def test_contributor_stats_exclude_lockfiles(repo):
    res = analyze_contributor_changes(repo, "alice", "alice@x.com", author_emails=["alice@x.com"])
    assert res["stats"]["totalCommits"] == 2
    assert "pnpm-lock.yaml" not in res["files"]
    assert res["excluded"]["pnpm-lock.yaml"] == "lockfile"
    assert all(len(ch["hash"]) == 40 for f in res["files"].values() for ch in f["changes"])


def test_shortlog_returns_other_contributors(repo):
    others = get_all_contributors_summary(repo, exclude_author="alice", exclude_emails=["alice@x.com"])
    assert others == {"bob": {"commits": 2, "email": "bob@y.com"}}


def test_other_contributor_details(repo):
    details = get_other_contributor_details(repo, exclude_author="alice", exclude_emails=["alice@x.com"])
    assert len(details) == 1
    bob = details[0]
    assert bob["name"] == "bob" and bob["commits"] == 2
    assert bob["top_dirs"][0] == "server/api"
    assert "server/db" in bob["top_dirs"]
    assert bob["recent_subjects"] == ["feat: bob db", "feat: bob api"]


def test_rename_map(repo):
    assert get_rename_map(repo) == {"src/old.ts": "src/lib/renamed.ts"}
