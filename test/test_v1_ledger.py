import os
import subprocess

from app.report.engines.v1.ledger import compute_ledger, expand_numstat_path
from test.test_git_inputs import _commit, _git


def test_expand_numstat_path():
    assert expand_numstat_path("src/{a => b}/x.ts") == "src/b/x.ts"
    assert expand_numstat_path("src/app/{ => (grp)}/login/page.tsx") == "src/app/(grp)/login/page.tsx"
    assert expand_numstat_path("src/{(old) => }/p.tsx") == "src/p.tsx"
    assert expand_numstat_path("old.ts => new.ts") == "new.ts"
    assert expand_numstat_path("plain/file.py") == "plain/file.py"


def _repo(tmp_path):
    r = str(tmp_path)
    _git(r, "init", "-q", "-b", "main")
    _commit(r, "alice", "alice@x.com", "feat: create service", {"src/service.ts": "a\n" * 40})
    _commit(r, "bob", "bob@y.com", "feat: bob page", {"src/page.tsx": "b\n" * 30})
    _commit(r, "alice", "alice@x.com", "fix: tweak page", {"src/page.tsx": "b\n" * 30 + "c\n" * 3})
    _commit(r, "bob", "bob@y.com", "feat: extend service", {"src/service.ts": "a\n" * 40 + "d\n" * 10})
    _commit(r, "alice", "alice@x.com", "style: prettier format", {"src/page.tsx": "B\n" * 33})
    with open(os.path.join(r, ".mailmap"), "w") as f:
        f.write("alice <alice@x.com>\n")
    return r


def test_ledger_levels_and_owners(tmp_path):
    r = _repo(tmp_path)
    head = set(subprocess.run(["git", "ls-files"], cwd=r, capture_output=True, text=True).stdout.split())
    led = compute_ledger(r, "alice", ["alice@x.com"], {}, head)
    svc, page = led.files["src/service.ts"], led.files["src/page.tsx"]
    assert svc.level == "created" and svc.first_author == "alice"
    assert round(svc.author_share, 2) == 0.8  # 40 / 50
    assert page.level == "minor"  # bob이 만들고 alice는 3줄 추가(포매팅 커밋 제외)
    assert page.first_author == "bob"
    assert led.excluded_format_commits == 1
    assert led.other_owned and led.other_owned[0].path == "src/page.tsx" and led.other_owned[0].owner == "bob"
