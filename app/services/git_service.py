import os
import re
import stat
import shutil
import subprocess
import requests
import uuid
from typing import Optional, Tuple
from collections import Counter
from datetime import datetime
from app.errors.exceptions import GitCloneException, GitAuthException, RepoNotFoundException


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


def get_commit_history(dir_path: str, author_name: str = None, author_email: str = None) -> list:
    all_commits = {}

    search_terms = []
    if author_email:
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
        current_file = None
        added_lines = []
        deleted_lines = []

        for line in diff_result.stdout.split("\n"):
            if line.startswith("diff --git"):
                if current_file:
                    files.append({
                        "path": current_file,
                        "added": added_lines,
                        "deleted": deleted_lines
                    })
                parts = line.split(" b/")
                current_file = parts[-1] if len(parts) > 1 else None
                added_lines = []
                deleted_lines = []
            elif line.startswith("+") and not line.startswith("+++"):
                added_lines.append(line[1:])
            elif line.startswith("-") and not line.startswith("---"):
                deleted_lines.append(line[1:])

        if current_file:
            files.append({
                "path": current_file,
                "added": added_lines,
                "deleted": deleted_lines
            })

        total_added = sum(len(f["added"]) for f in files)
        total_deleted = sum(len(f["deleted"]) for f in files)

        return {
            "files": files,
            "stats": {"added": total_added, "deleted": total_deleted}
        }
    except Exception:
        return {"files": [], "stats": {"added": 0, "deleted": 0}}


def analyze_contributor_changes(
    dir_path: str,
    author_name: str,
    author_email: str = None,
    max_added_lines: int = 999,
    max_deleted_lines: int = 999
) -> dict:
    commits = get_commit_history(dir_path, author_name, author_email)

    file_changes = {}
    commit_messages = []
    total_added = 0
    total_deleted = 0

    for commit in commits:
        commit_messages.append(commit["message"])
        diff = get_commit_diff(dir_path, commit["hash"])

        total_added += diff["stats"]["added"]
        total_deleted += diff["stats"]["deleted"]

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

    return {
        "commits": commits,
        "files": file_changes,
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


def get_all_contributors_summary(dir_path: str, exclude_author: str = None) -> dict:
    try:
        result = subprocess.run(
            ["git", "shortlog", "-sne", "--no-merges"],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            cwd=dir_path
        )

        if result.returncode != 0:
            return {}

        contributors = {}
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.strip().split("\t")
            if len(parts) >= 2:
                count = int(parts[0].strip())
                author_info = parts[1]
                author_name = author_info.split("<")[0].strip()

                if exclude_author and author_name.lower() == exclude_author.lower():
                    continue

                contributors[author_name] = {"commits": count}

        return contributors
    except Exception:
        return {}
