"""기준선 엔진: 기존 단일 프롬프트 + gemini_service 단일 호출."""
import json

from app.prompts.combined_report_prompt import get_combined_report_prompt
from app.report.context import ReportContext
from app.report.engines.base import EngineResult
from app.utils.build_versions import format_versions_table


def format_file_changes(ctx: ReportContext) -> str:
    lim = ctx.limits
    parts = []
    files = sorted(ctx.file_changes.items(), key=lambda x: x[1]["commits"], reverse=True)[: lim.max_files]
    for path, data in files:
        part = f"\n=== {path} (커밋 {data['commits']}회) ===\n"
        for change in data["changes"][: lim.max_commits_per_file]:
            part += f"[{change['date']}] {change['message']}\n"
            if change["added"]:
                part += "+추가:\n" + "\n".join(change["added"][: lim.max_added_lines]) + "\n"
            if change["deleted"]:
                part += "-삭제:\n" + "\n".join(change["deleted"][: lim.max_deleted_lines]) + "\n"
        parts.append(part)
    return "\n".join(parts)


def format_other_contributors(ctx: ReportContext) -> str:
    if not ctx.other_contributors:
        return "(다른 기여자 없음)"
    lines = []
    for o in ctx.other_contributors[:10]:
        line = f"- {o.name}: {o.commits}커밋"
        if o.top_dirs:
            line += f" | 주로 수정한 디렉터리: {', '.join(o.top_dirs)}"
        if o.recent_subjects:
            line += f" | 최근 커밋: {' / '.join(o.recent_subjects[:5])}"
        lines.append(line)
    return "\n".join(lines)


def build_legacy_prompt(ctx: ReportContext) -> str:
    f = ctx.facts
    return get_combined_report_prompt(
        repo_url=ctx.repo_url,
        author_name=ctx.author_name,
        total_commits=f.total_commits,
        user_commits=f.author_commit_count,
        contribution_ratio=f.contribution_ratio,
        tech_stack=json.dumps(ctx.tech_stack_detected, ensure_ascii=False, indent=2),
        total_files=f.project_code_files,
        total_lines=f.project_code_lines,
        tree_structure=ctx.tree_text,
        lines_added=f.author_added,
        lines_deleted=f.author_deleted,
        files_modified=f.author_files_modified,
        commit_messages="\n".join(c["message"] for c in ctx.author_commits[: ctx.limits.max_commit_messages]),
        file_changes=format_file_changes(ctx),
        other_contributors=format_other_contributors(ctx),
        development_period=f.project_period,
        test_code_count=f.test_files,
        available_techstacks=ctx.available_techstacks,
        build_versions=format_versions_table(ctx.build_versions),
        author_period=(
            f"{f.author_first_commit} ~ {f.author_last_commit} ({f.author_period})" if f.author_first_commit else "unknown"
        ),
    )


class LegacyEngine:
    name = "legacy"

    async def generate(self, ctx: ReportContext) -> EngineResult:
        from app.services.gemini_service import gemini_service

        usage: list = []
        raw = await gemini_service.generate_content(build_legacy_prompt(ctx), usage_sink=usage)
        techstacks = raw.pop("techstacks", []) if isinstance(raw, dict) else []
        return EngineResult(content=raw, techstacks=techstacks, usage=usage)
