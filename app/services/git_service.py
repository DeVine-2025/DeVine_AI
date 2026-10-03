import logging
import os
import re
import stat
import shutil
import subprocess
import requests
import uuid
from typing import Dict, List, Optional, Set, Tuple
from collections import Counter
from datetime import datetime
from app.errors.exceptions import GitCloneException, GitAuthException, RepoNotFoundException
from app.utils.diff_filter import skip_reason, truncate_line

logger = logging.getLogger(__name__)


def mask_token_in_message(message: str, token: str = None) -> str:
    if not message:
        return message

    if token:
        message = message.replace(token, "***TOKEN***")

    message = re.sub(r'(ghp_|gho_|ghu_|ghs_|ghr_)[A-Za-z0-9_]{30,}', '***TOKEN***', message)
    message = re.sub(r'x-access-token:[^@]+@', 'x-access-token:***TOKEN***@', message)
    message = re.sub(r'Bearer\s+[A-Za-z0-9_-]+', 'Bearer ***TOKEN***', message)

    return message


def get_github_user_from_token(github_token: str) -> Tuple[str, str]:
    try:
        response = requests.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/vnd.github.v3+json"
            },
            timeout=10
        )

        if response.status_code == 401:
            raise GitAuthException("GitHub 토큰이 유효하지 않습니다.")

        if response.status_code != 200:
            raise GitAuthException(f"GitHub API 오류: {response.status_code}")

        data = response.json()
        login = data.get("login")
        user_id = data.get("id")
        email = data.get("email")

        if not email:
            email = _get_github_user_email(github_token)

        noreply_email = f"{user_id}+{login}@users.noreply.github.com"

        if not email:
            email = noreply_email

        return login, email

    except requests.RequestException as e:
        raise GitAuthException(f"GitHub API 호출 실패: {str(e)}")


def _get_github_user_email(github_token: str) -> Optional[str]:
    try:
        response = requests.get(
            "https://api.github.com/user/emails",
            headers={
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/vnd.github.v3+json"
            },
            timeout=10
        )

        if response.status_code == 200:
            emails = response.json()
            for email_info in emails:
                if email_info.get("primary"):
                    return email_info.get("email")
            if emails:
                return emails[0].get("email")

        return None
    except Exception:
        return None


def parse_repo_url(repo_url: str) -> dict:
    match = re.search(r"github\.com[/:]([^/]+)/([^/]+?)(?:\.git)?$", repo_url)
    if not match:
        raise GitCloneException(f"잘못된 GitHub URL 형식: {repo_url}")

    return {"owner": match.group(1), "repo": match.group(2)}


def _get_github_user_node_id(login: str, github_token: str) -> Optional[str]:
    """GitHub REST API로 유저의 GraphQL node_id를 조회한다."""
    try:
        response = requests.get(
            f"https://api.github.com/users/{login}",
            headers={
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/vnd.github.v3+json",
            },
            timeout=10,
        )
        if response.status_code == 200:
            return response.json().get("node_id")
        return None
    except Exception:
        return None


def get_user_author_identities_from_github(
    owner: str, repo: str, login: str, github_token: str
) -> Optional[Dict[str, Set[str]]]:
    """GitHub GraphQL API로 특정 유저의 커밋에서 사용된 모든 author 이름/이메일을 조회한다.

    GraphQL의 history(author: { id }) 필터는 GitHub User ID 기반으로 매칭하므로
    계정에 등록된 모든 이메일 변형을 정확하게 잡아낸다.

    Returns:
        {"names": {"name1", "name2"}, "emails": {"email1", "email2"}} — 성공
        None — API 호출 실패 (호출자가 기존 방식으로 fallback)
    """
    node_id = _get_github_user_node_id(login, github_token)
    if not node_id:
        return None

    names: Set[str] = set()
    emails: Set[str] = set()
    cursor = None
    max_pages = 50

    try:
        for _ in range(max_pages):
            after_clause = f', after: "{cursor}"' if cursor else ""
            query = """
            query($owner: String!, $repo: String!, $authorId: ID!) {
              repository(owner: $owner, name: $repo) {
                defaultBranchRef {
                  target {
                    ... on Commit {
                      history(author: { id: $authorId }, first: 100%s) {
                        totalCount
                        pageInfo { hasNextPage endCursor }
                        nodes {
                          author { name email }
                        }
                      }
                    }
                  }
                }
              }
            }
            """ % after_clause

            response = requests.post(
                "https://api.github.com/graphql",
                headers={
                    "Authorization": f"Bearer {github_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "query": query,
                    "variables": {
                        "owner": owner,
                        "repo": repo,
                        "authorId": node_id,
                    },
                },
                timeout=15,
            )

            if response.status_code != 200:
                return None

            result = response.json()
            if "errors" in result:
                return None

            history = (
                result.get("data", {})
                .get("repository", {})
                .get("defaultBranchRef", {})
                .get("target", {})
                .get("history", {})
            )

            for node in history.get("nodes", []):
                author = node.get("author", {})
                if author.get("name"):
                    names.add(author["name"])
                if author.get("email"):
                    emails.add(author["email"])

            page_info = history.get("pageInfo", {})
            if not page_info.get("hasNextPage"):
                break
            cursor = page_info.get("endCursor")

        return {"names": names, "emails": emails}
    except Exception:
        return None


def clone_repository(repo_url: str, github_token: str, temp_base_dir: str = "./temp") -> str:
    repo_info = parse_repo_url(repo_url)
    owner = repo_info["owner"]
    repo = repo_info["repo"]

    unique_id = uuid.uuid4().hex[:8]
    temp_dir = os.path.join(temp_base_dir, f"git-{owner}-{repo}-{unique_id}")

    os.makedirs(temp_dir, exist_ok=True)

    clone_url = f"https://x-access-token:{github_token}@github.com/{owner}/{repo}.git"

    try:
        result = subprocess.run(
            ["git", "clone", "--single-branch", clone_url, temp_dir],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=300
        )

        if result.returncode != 0:
            error_msg = result.stderr.lower()

            if "authentication" in error_msg or "401" in error_msg:
                raise GitAuthException("GitHub 인증 실패. 토큰을 확인해주세요.")

            if "not found" in error_msg or "404" in error_msg:
                raise RepoNotFoundException(f"레포지토리를 찾을 수 없습니다: {owner}/{repo}")

            raise GitCloneException(f"Git 클론 실패: {mask_token_in_message(result.stderr, github_token)}")

        return temp_dir

    except subprocess.TimeoutExpired:
        cleanup_directory(temp_dir)
        raise GitCloneException("Git 클론 시간 초과")

    except (GitAuthException, RepoNotFoundException, GitCloneException):
        cleanup_directory(temp_dir)
        raise

    except Exception as e:
        cleanup_directory(temp_dir)
        raise GitCloneException(f"Git 클론 중 오류 발생: {mask_token_in_message(str(e), github_token)}")


def cleanup_directory(dir_path: str):
    def remove_readonly(func, path, excinfo):
        try:
            os.chmod(path, stat.S_IWRITE)
            func(path)
        except Exception:
            pass

    try:
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path, onerror=remove_readonly)
    except Exception:
        pass


def create_mailmap(dir_path: str, canonical_name: str, emails: List[str]):
    """클론된 레포에 .mailmap 파일 생성. 첫 번째 이메일을 canonical로 사용."""
    if not emails:
        return
    canonical_email = emails[0]
    lines = []
    # 같은 이메일로 다른 이름을 사용한 커밋도 canonical_name으로 통합
    lines.append(f"{canonical_name} <{canonical_email}>")
    for email in emails[1:]:
        lines.append(f"{canonical_name} <{canonical_email}> <{email}>")
    mailmap_path = os.path.join(dir_path, ".mailmap")
    with open(mailmap_path, "w") as f:
        f.write("\n".join(lines) + "\n")


def get_commit_count(dir_path: str) -> int:
    try:
        result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            cwd=dir_path
        )
        return int(result.stdout.strip()) if result.returncode == 0 else 0
    except Exception:
        return 0


def get_commit_history(dir_path: str, author_name: str = None, author_email: str = None, author_emails: List[str] = None) -> list:
    all_commits = {}

    search_terms = []
    if author_emails:
        for email in author_emails:
            search_terms.append(email)
            if "noreply.github.com" in email:
                parts = email.split("+")
                if len(parts) > 1:
                    username_part = parts[1].split("@")[0]
                    search_terms.append(username_part)
    elif author_email:
        search_terms.append(author_email)
        if "noreply.github.com" in author_email:
            parts = author_email.split("+")
            if len(parts) > 1:
                username_part = parts[1].split("@")[0]
                search_terms.append(username_part)
    if author_name:
        search_terms.append(author_name)

    if not search_terms:
        return []

    for search_term in search_terms:
        try:
            cmd = [
                "git", "log",
                "--format=%H|%an|%ae|%aI|%s",
                "--no-merges",
                "--author", search_term
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                cwd=dir_path
            )

            if result.returncode != 0:
                continue

            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split("|", 4)
                if len(parts) >= 5:
                    commit_hash = parts[0]
                    if commit_hash not in all_commits:
                        all_commits[commit_hash] = {
                            "hash": commit_hash,
                            "author": parts[1],
                            "email": parts[2],
                            "date": parts[3],
                            "message": parts[4]
                        }
        except Exception:
            continue

    sorted_commits = sorted(all_commits.values(), key=lambda x: x["date"], reverse=True)
    return sorted_commits


def get_commit_diff(dir_path: str, commit_hash: str) -> dict:
    """커밋 diff를 파일별 추가/삭제 줄로 나눈다.

    lock 파일, 에셋, 빌드 생성물은 diff와 통계에서 모두 뺀다(excluded에 사유 기록).
    삭제된 파일은 통계에는 넣고 내용(삭제 줄)은 넣지 않는다. 한 줄은 MAX_LINE_CHARS로 자른다.
    """
    try:
        diff_result = subprocess.run(
            ["git", "show", "--format=", "--unified=3", commit_hash],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            cwd=dir_path
        )

        files = []
        excluded = {}
        current = None
        total_added = 0
        total_deleted = 0

        def flush():
            if current and current["reason"] is None:
                files.append({"path": current["path"], "added": current["added"], "deleted": current["deleted"]})

        for line in diff_result.stdout.split("\n"):
            if line.startswith("diff --git"):
                flush()
                parts = line.split(" b/")
                path = parts[-1] if len(parts) > 1 else None
                reason = skip_reason(path) if path else "unknown"
                if path and reason:
                    excluded[path] = reason
                current = {"path": path, "reason": reason, "added": [], "deleted": [], "file_deleted": False}
            elif current is None:
                continue
            elif line.startswith("deleted file mode"):
                current["file_deleted"] = True
            elif line.startswith("+") and not line.startswith("+++"):
                if current["reason"] is None:
                    total_added += 1
                    current["added"].append(truncate_line(line[1:]))
            elif line.startswith("-") and not line.startswith("---"):
                if current["reason"] is None:
                    total_deleted += 1
                    if not current["file_deleted"]:
                        current["deleted"].append(truncate_line(line[1:]))
        flush()

        return {
            "files": files,
            "excluded": excluded,
            "stats": {"added": total_added, "deleted": total_deleted}
        }
    except Exception:
        return {"files": [], "excluded": {}, "stats": {"added": 0, "deleted": 0}}


def analyze_contributor_changes(
    dir_path: str,
    author_name: str,
    author_email: str = None,
    author_emails: List[str] = None,
    max_added_lines: int = 999,
    max_deleted_lines: int = 999
) -> dict:
    commits = get_commit_history(dir_path, author_name, author_email, author_emails)

    file_changes = {}
    commit_messages = []
    excluded = {}
    total_added = 0
    total_deleted = 0

    for commit in commits:
        commit_messages.append(commit["message"])
        diff = get_commit_diff(dir_path, commit["hash"])

        total_added += diff["stats"]["added"]
        total_deleted += diff["stats"]["deleted"]
        excluded.update(diff.get("excluded", {}))

        for file in diff["files"]:
            path = file["path"]
            if path not in file_changes:
                file_changes[path] = {
                    "commits": 0,
                    "totalAdded": 0,
                    "totalDeleted": 0,
                    "changes": []
                }

            file_changes[path]["commits"] += 1
            file_changes[path]["totalAdded"] += len(file["added"])
            file_changes[path]["totalDeleted"] += len(file["deleted"])
            file_changes[path]["changes"].append({
                "date": commit["date"][:10],
                "message": commit["message"],
                "added": file["added"][:max_added_lines],
                "deleted": file["deleted"][:max_deleted_lines]
            })

    if excluded:
        logger.info(f"diff 필터로 제외한 파일 {len(excluded)}개: {dict(list(excluded.items())[:20])}")

    return {
        "commits": commits,
        "files": file_changes,
        "excluded": excluded,
        "stats": {
            "totalCommits": len(commits),
            "totalAdded": total_added,
            "totalDeleted": total_deleted,
            "filesModified": len(file_changes)
        },
        "commitMessages": commit_messages
    }


def get_development_period(dir_path: str) -> str:
    try:
        first_result = subprocess.run(
            ["git", "log", "--diff-filter=A", "--format=%aI", "--all"],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            cwd=dir_path
        )

        last_result = subprocess.run(
            ["git", "log", "--format=%aI", "-1"],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            cwd=dir_path
        )

        if first_result.returncode != 0 or last_result.returncode != 0:
            return "알 수 없음"

        dates = first_result.stdout.strip().split('\n')
        dates = [d[:10] for d in dates if d.strip()]

        if not dates:
            return "알 수 없음"

        dates.sort()
        first_date = dates[0]
        last_date = last_result.stdout.strip()[:10]

        first_dt = datetime.strptime(first_date, "%Y-%m-%d")
        last_dt = datetime.strptime(last_date, "%Y-%m-%d")

        days = (last_dt - first_dt).days

        if days < 7:
            return "약 1주일 미만"
        elif days < 30:
            weeks = days // 7
            return f"약 {weeks}주"
        elif days < 365:
            months = days // 30
            return f"약 {months}개월"
        else:
            years = days // 365
            remaining_months = (days % 365) // 30
            if remaining_months > 0:
                return f"약 {years}년 {remaining_months}개월"
            return f"약 {years}년"

    except Exception:
        return "알 수 없음"


def get_all_contributors_summary(dir_path: str, exclude_author: str = None, exclude_emails: List[str] = None) -> dict:
    try:
        result = subprocess.run(
            ["git", "shortlog", "-sne", "--no-merges", "HEAD"],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            cwd=dir_path
        )

        if result.returncode != 0:
            return {}

        exclude_emails_lower = [e.lower() for e in exclude_emails] if exclude_emails else []

        contributors = {}
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.strip().split("\t")
            if len(parts) >= 2:
                count = int(parts[0].strip())
                author_info = parts[1]
                author_name = author_info.split("<")[0].strip()

                email_match = re.search(r'<(.+?)>', author_info)
                author_email_parsed = email_match.group(1) if email_match else ""

                if exclude_author and author_name.lower() == exclude_author.lower():
                    continue
                if exclude_emails_lower and author_email_parsed.lower() in exclude_emails_lower:
                    continue

                if author_name in contributors:
                    contributors[author_name]["commits"] += count
                else:
                    contributors[author_name] = {"commits": count, "email": author_email_parsed}

        return contributors
    except Exception:
        return {}


def get_other_contributor_details(
    dir_path: str,
    exclude_author: str = None,
    exclude_emails: List[str] = None,
    max_contributors: int = 10,
    top_dirs: int = 5,
    max_subjects: int = 10,
) -> List[dict]:
    """다른 기여자별 커밋 수, 많이 고친 디렉터리, 최근 커밋 제목. 기여 귀속(P2) 판단용."""
    summary = get_all_contributors_summary(dir_path, exclude_author=exclude_author, exclude_emails=exclude_emails)
    result = []
    for name, data in sorted(summary.items(), key=lambda x: -x[1]["commits"])[:max_contributors]:
        try:
            out = subprocess.run(
                ["git", "log", "--no-merges", "--use-mailmap", "-F", "--author", data.get("email") or name,
                 "--format=@@%s", "--name-only", "HEAD"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=dir_path,
            ).stdout
        except Exception:
            out = ""
        subjects, dirs = [], Counter()
        for line in out.splitlines():
            if line.startswith("@@"):
                subjects.append(line[2:])
            elif line.strip() and not skip_reason(line):
                parts = line.split("/")
                dirs["/".join(parts[:2]) if len(parts) > 2 else (parts[0] if len(parts) > 1 else ".")] += 1
        result.append({
            "name": name,
            "commits": data["commits"],
            "top_dirs": [d for d, _ in dirs.most_common(top_dirs)],
            "recent_subjects": subjects[:max_subjects],
        })
    return result


def get_rename_map(dir_path: str) -> Dict[str, str]:
    """옛 경로 → HEAD 경로. 여러 번 바뀐 경로는 끝까지 따라간다. HEAD에 다시 생긴 경로는 매핑하지 않는다."""
    try:
        out = subprocess.run(
            ["git", "log", "-M", "--name-status", "--format=", "HEAD"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=dir_path,
        ).stdout
        head = set(subprocess.run(
            ["git", "ls-files"], capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=dir_path,
        ).stdout.splitlines())
    except Exception:
        return {}
    direct: Dict[str, str] = {}
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and parts[0].startswith("R"):
            direct.setdefault(parts[1], parts[2])
    resolved = {}
    for old in direct:
        if old in head:
            continue
        cur, seen = old, set()
        while cur in direct and cur not in seen:
            seen.add(cur)
            cur = direct[cur]
        if cur in head:
            resolved[old] = cur
    return resolved
