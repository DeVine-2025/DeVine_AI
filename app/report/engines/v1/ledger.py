"""기여 원장 (회의 자료 S10).

파일별로 최초 작성자, 작성자 추가 줄 비율, 기여 수준(created / major / minor)을 git으로 계산한다.
- `git log -M --numstat --use-mailmap` 한 번으로 계산한다. 포매팅 커밋은 뺀다.
- blame(-w -M -C)은 근거 카드에 들어간 파일에만 적용해 "현재 줄" 기준 비율로 보정한다.
LLM에 넘겨 표현 규칙(minor면 "구현"이 아니라 "개선")과 notImplemented 근거(S12)에 쓴다.
"""
import re
import subprocess
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Set

from app.utils.diff_filter import skip_reason

FORMAT_COMMIT = re.compile(
    r"^(style|format)\b|^chore\(format\)|prettier|eslint\s*--fix|lint\s*fix|포맷|포매팅|코드\s*정리|indent|whitespace",
    re.IGNORECASE,
)
MAJOR_SHARE = 0.5
MAX_OTHER_OWNED = 40
MAX_BLAME_FILES = 40
LEVEL_RANK = {"created": 0, "major": 1, "minor": 2}


@dataclass
class FileOwnership:
    path: str
    level: str
    author_share: float
    first_author: str
    author_added: int
    total_added: int
    blame_share: Optional[float] = None


@dataclass
class OtherOwned:
    path: str
    owner: str
    share: float
    total_added: int


@dataclass
class Ledger:
    files: Dict[str, FileOwnership] = field(default_factory=dict)  # 작성자가 건드린 HEAD 파일
    other_owned: List[OtherOwned] = field(default_factory=list)  # 작성자 몫이 아닌, 다른 기여자가 주로 쓴 파일
    excluded_format_commits: int = 0


def expand_numstat_path(p: str) -> str:
    """numstat의 이름 변경 표기(`a/{x => y}/b`, `old => new`)를 새 경로로 바꾼다."""
    if "{" in p and " => " in p:
        p = re.sub(r"\{([^{}]*) => ([^{}]*)\}", lambda m: m.group(2), p)
        return re.sub(r"/{2,}", "/", p).strip("/")
    if " => " in p:
        return p.split(" => ", 1)[1]
    return p


def _level(created: bool, share: float) -> str:
    if created:
        return "created"
    return "major" if share >= MAJOR_SHARE else "minor"


def compute_ledger(
    dir_path: str,
    author_name: str,
    author_emails: Iterable[str],
    rename_map: Dict[str, str],
    head_files: Set[str],
) -> Ledger:
    emails = {e.lower() for e in author_emails}
    out = subprocess.run(
        ["git", "log", "-M", "--no-merges", "--numstat", "--use-mailmap", "--format=@@%H%x09%aE%x09%aN%x09%s", "HEAD"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=dir_path,
    ).stdout

    added: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    first_author: Dict[str, str] = {}
    first_is_author: Dict[str, bool] = {}
    touched_by_author: Set[str] = set()
    format_commits = 0
    who, is_author, skip_commit = "", False, False

    for line in out.splitlines():
        if line.startswith("@@"):
            _, email, name, subject = (line[2:].split("\t", 3) + ["", "", ""])[:4]
            who = name or email
            is_author = email.lower() in emails or name == author_name
            skip_commit = bool(FORMAT_COMMIT.search(subject))
            format_commits += skip_commit and is_author
            continue
        parts = line.split("\t")
        if len(parts) != 3 or parts[0] == "-":
            continue
        path = expand_numstat_path(parts[2])
        path = rename_map.get(path, path)
        if path not in head_files or skip_reason(path) or skip_commit:
            continue
        added[path][who] += int(parts[0])
        first_author[path] = who  # 최신 → 과거 순으로 읽으므로 마지막 값이 최초 작성자
        first_is_author[path] = is_author
        if is_author:
            touched_by_author.add(path)
            added[path]["__author__"] += int(parts[0])

    ledger = Ledger(excluded_format_commits=format_commits)
    for path, by_who in added.items():
        author_lines = by_who.get("__author__", 0)
        total = sum(v for k, v in by_who.items() if k != "__author__")
        share = author_lines / total if total else 0.0
        if path in touched_by_author:
            ledger.files[path] = FileOwnership(
                path=path,
                level=_level(first_is_author.get(path, False), share),
                author_share=share,
                first_author=first_author.get(path, ""),
                author_added=author_lines,
                total_added=total,
            )
        if share < MAJOR_SHARE and not first_is_author.get(path, False) and total > 0:
            others = {k: v for k, v in by_who.items() if k != "__author__" and v > 0}
            # 작성자 줄은 others에도 이름으로 들어 있으므로 빼고 본다
            for k in list(others):
                if k == author_name:
                    others.pop(k)
            if others:
                owner, lines = max(others.items(), key=lambda kv: kv[1])
                if lines / total >= MAJOR_SHARE:
                    ledger.other_owned.append(OtherOwned(path=path, owner=owner, share=lines / total, total_added=total))
    ledger.other_owned.sort(key=lambda o: -o.total_added)
    ledger.other_owned = ledger.other_owned[:MAX_OTHER_OWNED]
    return ledger


def _blame_share(dir_path: str, path: str, emails: Set[str], author_name: str) -> Optional[float]:
    try:
        out = subprocess.run(
            ["git", "blame", "-w", "-M", "-C", "--line-porcelain", "HEAD", "--", path],
            capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=dir_path, timeout=20,
        ).stdout
    except Exception:
        return None
    total = mine = 0
    name = ""
    for line in out.splitlines():
        if line.startswith("author "):
            name = line[7:]
        elif line.startswith("author-mail "):
            total += 1
            mail = line[12:].strip("<>").lower()
            mine += mail in emails or name == author_name
    return mine / total if total else None


def refine_with_blame(dir_path: str, ledger: Ledger, paths: Iterable[str], author_name: str, author_emails: Iterable[str]) -> int:
    """카드에 나온 파일만 blame으로 현재 줄 비율을 구해 수준을 보정한다. 보정한 파일 수를 돌려준다."""
    emails = {e.lower() for e in author_emails}
    targets = [p for p in dict.fromkeys(paths) if p in ledger.files][:MAX_BLAME_FILES]
    with ThreadPoolExecutor(max_workers=8) as pool:
        shares = list(pool.map(lambda p: _blame_share(dir_path, p, emails, author_name), targets))
    changed = 0
    for path, share in zip(targets, shares):
        if share is None:
            continue
        f = ledger.files[path]
        f.blame_share = share
        if f.level != "created":
            new = _level(False, max(f.author_share, share))
            changed += new != f.level
            f.level = new
    return changed
