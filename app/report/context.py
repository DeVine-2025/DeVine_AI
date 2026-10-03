"""리포트 생성 입력(ReportContext). 모든 엔진이 같은 입력을 받는다."""
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class AnalysisLimits:
    max_commit_messages: int
    max_files: int
    max_commits_per_file: int
    max_added_lines: int
    max_deleted_lines: int


def calculate_dynamic_limits(user_commits: int, files_modified: int) -> AnalysisLimits:
    if user_commits < 50 and files_modified < 30:
        return AnalysisLimits(999, 999, 999, 999, 999)
    if user_commits < 200 and files_modified < 100:
        return AnalysisLimits(100, 80, 10, 100, 50)
    if user_commits < 500:
        return AnalysisLimits(80, 60, 5, 50, 30)
    return AnalysisLimits(50, 40, 3, 30, 20)


def format_period(days: int) -> str:
    if days < 7:
        return "약 1주일 미만"
    if days < 30:
        return f"약 {days // 7}주"
    if days < 365:
        return f"약 {days // 30}개월"
    years, months = days // 365, (days % 365) // 30
    return f"약 {years}년 {months}개월" if months else f"약 {years}년"


@dataclass
class ReportFacts:
    """코드가 계산한 숫자. LLM이 만들지 않고 후처리가 그대로 채운다."""

    total_commits: int = 0
    author_commit_count: int = 0
    contribution_ratio: float = 0.0
    author_added: int = 0
    author_deleted: int = 0
    author_files_modified: int = 0
    project_code_files: int = 0
    project_code_lines: int = 0
    project_period: str = "알 수 없음"
    author_first_commit: Optional[str] = None
    author_last_commit: Optional[str] = None
    author_period: str = "알 수 없음"
    test_files: int = 0


@dataclass
class OtherContributor:
    name: str
    commits: int
    top_dirs: List[str] = field(default_factory=list)
    recent_subjects: List[str] = field(default_factory=list)


@dataclass
class ReportContext:
    repo_url: str
    project_name: str
    author_name: str
    author_emails: List[str]
    available_techstacks: List[str] = field(default_factory=list)
    author_commits: List[dict] = field(default_factory=list)  # {hash, date, message}
    file_changes: Dict[str, dict] = field(default_factory=dict)  # path → {commits, totalAdded, totalDeleted, changes[]}
    facts: ReportFacts = field(default_factory=ReportFacts)
    tree_text: str = ""
    head_files: List[str] = field(default_factory=list)
    rename_map: Dict[str, str] = field(default_factory=dict)
    build_versions: Dict[str, str] = field(default_factory=dict)
    tech_stack_detected: Dict[str, List[str]] = field(default_factory=dict)
    other_contributors: List[OtherContributor] = field(default_factory=list)
    excluded_files: Dict[str, str] = field(default_factory=dict)  # diff 필터로 뺀 경로 → 사유
    limits: AnalysisLimits = field(default_factory=lambda: calculate_dynamic_limits(0, 0))
    dir_path: str = ""

    @property
    def head_file_set(self) -> set:
        cached = getattr(self, "_head_file_set", None)
        if cached is None:
            cached = set(self.head_files)
            object.__setattr__(self, "_head_file_set", cached)
        return cached


def _author_period(commits: List[dict]) -> tuple:
    dates = sorted(c["date"][:10] for c in commits if c.get("date"))
    if not dates:
        return None, None, "알 수 없음"
    days = (datetime.strptime(dates[-1], "%Y-%m-%d") - datetime.strptime(dates[0], "%Y-%m-%d")).days
    return dates[0], dates[-1], format_period(days)


def build_context(
    dir_path: str,
    repo_url: str,
    author_name: str,
    author_emails: List[str],
    available_techstacks: Optional[List[str]] = None,
) -> ReportContext:
    """clone된 레포에서 리포트 입력을 모은다. 기존 analyzer의 수집부 + 입력 수정(0-5)."""
    from app.services.git_service import (
        analyze_contributor_changes,
        get_commit_count,
        get_development_period,
        get_other_contributor_details,
        get_rename_map,
        parse_repo_url,
    )
    from app.utils.build_versions import parse_build_versions
    from app.utils.file_reader import count_lines, count_test_files, get_code_files, get_git_tracked_files
    from app.utils.tech_detector import detect_tech_stack
    from app.utils.tree_builder import build_project_tree

    author_email = author_emails[0] if author_emails else None
    code_files = get_code_files(dir_path)
    head_files = get_git_tracked_files(dir_path)
    rename_map = get_rename_map(dir_path)

    changes = analyze_contributor_changes(dir_path, author_name, author_email, author_emails=author_emails)
    stats = changes["stats"]
    first, last, author_period = _author_period(changes["commits"])
    total_commits = get_commit_count(dir_path)

    head_set = set(head_files)
    author_head_files = sorted({rename_map.get(p, p) for p in changes["files"]} & head_set)

    try:
        project_name = parse_repo_url(repo_url)["repo"]
    except Exception:
        project_name = repo_url.rstrip("/").split("/")[-1].removesuffix(".git")

    facts = ReportFacts(
        total_commits=total_commits,
        author_commit_count=stats["totalCommits"],
        contribution_ratio=round(stats["totalCommits"] / total_commits * 100, 1) if total_commits else 0.0,
        author_added=stats["totalAdded"],
        author_deleted=stats["totalDeleted"],
        author_files_modified=stats["filesModified"],
        project_code_files=len(code_files),
        project_code_lines=sum(count_lines(os.path.join(dir_path, f)) for f in code_files),
        project_period=get_development_period(dir_path),
        author_first_commit=first,
        author_last_commit=last,
        author_period=author_period,
        test_files=count_test_files(dir_path),
    )
    limits = calculate_dynamic_limits(stats["totalCommits"], stats["filesModified"])
    logger.info(
        f"컨텍스트 수집: 작성자 커밋 {stats['totalCommits']}개, 파일 {stats['filesModified']}개, "
        f"제외 파일 {len(changes.get('excluded', {}))}개, 제한값 {limits}"
    )
    return ReportContext(
        repo_url=repo_url,
        project_name=project_name,
        author_name=author_name,
        author_emails=list(author_emails),
        available_techstacks=list(available_techstacks or []),
        author_commits=[{"hash": c["hash"], "date": c["date"], "message": c["message"]} for c in changes["commits"]],
        file_changes=changes["files"],
        facts=facts,
        tree_text=build_project_tree(dir_path, focus_paths=author_head_files),
        head_files=head_files,
        rename_map=rename_map,
        build_versions=parse_build_versions(dir_path, head_files),
        tech_stack_detected=detect_tech_stack(dir_path),
        other_contributors=[OtherContributor(**o) for o in get_other_contributor_details(
            dir_path, exclude_author=author_name, exclude_emails=author_emails
        )],
        excluded_files=changes.get("excluded", {}),
        limits=limits,
        dir_path=dir_path,
    )
