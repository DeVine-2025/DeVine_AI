"""평가 기준값(정답 쪽 사실) 계산.

엔진 코드와 독립적으로 git만으로 계산한다. 평가 대상 코드가 바뀌어도 기준이 흔들리지 않게 하기 위함이다.
"""
import json
import os
import re
import subprocess

_IDENT = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]{3,}\b")


def _git(repo: str, *args: str) -> str:
    out = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return out.stdout


def _author_args(author: dict) -> list[str]:
    args = ["-F"]
    for term in [author["name"], *author["emails"]]:
        args += ["--author", term]
    return args


def rename_map(repo: str) -> dict[str, str]:
    """옛 경로 → HEAD 경로. 최신 커밋부터 거꾸로 읽으며 체인을 잇는다."""
    out = _git(repo, "log", "-M", "--name-status", "--format=", "HEAD")
    direct: dict[str, str] = {}
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and parts[0].startswith("R"):
            old, new = parts[1], parts[2]
            direct.setdefault(old, new)
    resolved = {}
    for old in direct:
        cur, seen = old, set()
        while cur in direct and cur not in seen:
            seen.add(cur)
            cur = direct[cur]
        resolved[old] = cur
    return resolved


def is_identifier(tok: str) -> bool:
    """코드 식별자처럼 생긴 토큰: camelCase, PascalCase(대문자 2개 이상), snake_case."""
    if "_" in tok.strip("_"):
        return True
    return any(c.isupper() for c in tok[1:]) and any(c.islower() for c in tok)


def dep_names(repo: str) -> list[str]:
    names: set[str] = set()
    for path in _git(repo, "ls-files").splitlines():
        base = os.path.basename(path)
        full = os.path.join(repo, path)
        if "node_modules" in path:
            continue
        try:
            if base == "package.json":
                data = json.load(open(full, encoding="utf-8"))
                names.update(data.get("dependencies", {}))
                names.update(data.get("devDependencies", {}))
            elif base == "requirements.txt":
                for line in open(full, encoding="utf-8"):
                    m = re.match(r"\s*([A-Za-z0-9_.\-]+)", line)
                    if m and not line.strip().startswith("#"):
                        names.add(m.group(1).lower())
            elif base in ("build.gradle", "build.gradle.kts"):
                for m in re.finditer(r"['\"]([\w.\-]+):([\w.\-]+)(?::[\w.\-]+)?['\"]", open(full, encoding="utf-8").read()):
                    names.add(m.group(2))
        except Exception:
            continue
    return sorted(names)


def compute_case_facts(repo: str, author: dict) -> dict:
    head_files = [f for f in _git(repo, "ls-files").splitlines() if f]
    head_set = set(head_files)
    rmap = rename_map(repo)
    raw_author_files = {
        f for f in _git(repo, "log", "--no-merges", "--format=", "--name-only", *_author_args(author), "HEAD").splitlines() if f
    }
    author_files = sorted({rmap.get(f, f) for f in raw_author_files} & head_set)

    idents: set[str] = set()
    diff = _git(repo, "log", "--no-merges", "-p", "--format=", *_author_args(author), "HEAD")
    for line in diff.splitlines():
        if line.startswith("+") and not line.startswith("+++") and len(line) < 500:
            idents.update(t for t in _IDENT.findall(line) if is_identifier(t))
        if len(idents) > 30000:
            break
    author_commits = len([c for c in _git(repo, "log", "--no-merges", "--format=%H", *_author_args(author), "HEAD").splitlines() if c])
    return {
        "head_files": head_files,
        "author_files": author_files,
        "author_commits": author_commits,
        "rename_map": rmap,
        "identifiers": sorted(idents),
        "dep_names": dep_names(repo),
    }
