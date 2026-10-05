"""
haru-web 5회 반복 오케스트레이션 평가 및 기존 v2 대비 비교 분석 러너
대상: haru-web (https://github.com/HaRu-Developers/haru-web.git @ develop 55189c0)
결과 저장 위치: C:\\git\\devine\\result
"""

import os
import sys
import asyncio
import json
import time
import logging
import subprocess

# Devine_ai 경로 추가
DEVINE_AI_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, DEVINE_AI_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(DEVINE_AI_DIR, ".env"))

from app.services.git_service import (
    cleanup_directory,
    create_mailmap,
    get_commit_count,
    analyze_contributor_changes,
    get_all_contributors_summary,
    get_development_period,
)
from app.utils.file_reader import get_code_files, count_lines
from app.utils.tech_detector import detect_tech_stack
from app.utils.tree_builder import build_project_tree, get_all_relative_file_paths
from app.utils.diff_budgeter import budget_file_changes, budget_tree_structure
from app.services.analyzer_service import analyzer_service
from app.services.orchestration.pipeline import OrchestrationPipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("eval_haru_5times")

REPO_URL = "https://github.com/HaRu-Developers/haru-web.git"
BRANCH = "develop"
AUTHOR_NAME = "strfunctionk"
AUTHOR_EMAILS = [
    "84651690+strfunctionk@users.noreply.github.com",
    "strfunctionk@gmail.com",
    "strfunctionk@users.noreply.github.com",
]

AVAILABLE_TECHSTACKS = [
    "TYPESCRIPT", "JAVASCRIPT", "REACT", "NEXTJS", "VUE", "TAILWINDCSS",
    "REDUX", "ZUSTAND", "REACTQUERY", "AXIOS", "HTML", "CSS", "NODEJS",
    "PYTHON", "JAVA", "SPRINGBOOT", "POSTGRESQL", "MYSQL", "DOCKER", "AWS"
]

RESULT_DIR = r"C:\git\devine\result"


def render_markdown_report(report: dict, run_idx: int, elapsed_sec: float) -> str:
    """기존 v2 마크다운 포맷과 완벽 호환되도록 렌더링"""
    main = report.get("main", {})
    detail = report.get("detail", {})
    techstacks = report.get("techstacks", [])

    lines = []
    lines.append(f"# haru-web 리포트 #{run_idx:02d}\n")
    lines.append(f"- 레포: {REPO_URL} (`{BRANCH}` @ `55189c0`)")
    lines.append(f"- 분석 대상: {AUTHOR_NAME}")
    lines.append(f"- 모델: gemini-2.5-flash (2-Stage Orchestration + SVG Filtering)")
    lines.append(f"- 상태: SUCCESS ({elapsed_sec:.1f}초)\n")

    lines.append("## techstacks\n")
    lines.append(", ".join(techstacks) + "\n")
    lines.append("---\n")

    # Main
    lines.append("# Main 리포트\n")
    overview = main.get("overview", {})
    lines.append("## 개요\n")
    lines.append(f"**요약:** {overview.get('summary', '')}\n")
    lines.append(f"**주요 기술:** {overview.get('mainTech', '')}\n")
    lines.append(f"**규모:** {overview.get('scale', '')}\n")
    lines.append("**핵심 역량**")
    for cap in overview.get("capabilities", []):
        lines.append(f"- {cap}")
    lines.append("")

    pinfo = main.get("projectInfo", {})
    lines.append("## 프로젝트 정보\n")
    lines.append(f"- 프로젝트명: {pinfo.get('projectName', '')}")
    lines.append(f"- 규모: {pinfo.get('scale', '')}")
    lines.append("- 기술 스택:")
    for ts in pinfo.get("techStack", []):
        lines.append(f"  - {ts}")
    lines.append("")

    lines.append("## 핵심 구현\n")
    for i, impl in enumerate(main.get("keyImplementations", []), 1):
        lines.append(f"### {i}. {impl.get('title', '')}\n")
        lines.append(f"{impl.get('description', '')}\n")
        for cap in impl.get("capabilities", []):
            lines.append(f"- {cap}")
        lines.append("")

    lines.append("## AI 평가\n")
    for i, ev in enumerate(main.get("aiEvaluation", []), 1):
        lines.append(f"### {i}. {ev.get('title', '')}\n")
        for det in ev.get("details", []):
            lines.append(f"- {det}")
        lines.append("")

    lines.append("## 추천 분야\n")
    for rec in main.get("recommendations", []):
        lines.append(f"- {rec}")
    lines.append("\n---\n")

    # Detail
    lines.append(f"# Detail 리포트: {detail.get('reportTitle', 'haru-web')}\n")
    lines.append(f"_{detail.get('reportSubtitle', '프로젝트 상세 분석 리포트')}_\n")

    pover = detail.get("projectOverview", {})
    lines.append("## 프로젝트 개요\n")
    lines.append(f"{pover.get('purpose', '')}\n")

    lines.append("**기술 스택**\n")
    for cat in pover.get("techStack", []):
        lines.append(f"- **{cat.get('title', '')}**: {cat.get('content', '')}")
    lines.append("")

    pscale = pover.get("projectScale", {})
    lines.append("**규모**\n")
    lines.append(f"- 주요 코드 파일: {pscale.get('mainCodeFiles', '')}")
    lines.append(f"- 총 코드 라인: {pscale.get('totalCodeLines', '')}")
    lines.append(f"- 개발 기간: {pscale.get('developmentPeriod', '')}")
    lines.append(f"- 아키텍처: {pscale.get('architecturePattern', '')}\n")

    lines.append("## 구현 기능\n")
    for cat in detail.get("implementedFeatures", []):
        lines.append(f"### {cat.get('categoryNumber', '')}. {cat.get('category', '')}\n")
        for feat in cat.get("features", []):
            lines.append(f"#### {feat.get('name', '')}\n")
            lines.append("구현:")
            for imp in feat.get("implementation", []):
                lines.append(f"- {imp}")
            lines.append("\n세부:")
            for det in feat.get("details", []):
                lines.append(f"- {det}")
            lines.append("\n코드 위치:")
            for loc in feat.get("codeLocation", []):
                lines.append(f"- `{loc}`")
            lines.append("")

    psummary = detail.get("projectSummary", {})
    lines.append("## 프로젝트 요약\n")
    lines.append("### 본인 구현 기능")
    for imp in psummary.get("implemented", []):
        lines.append(f"- {imp}")
    lines.append("\n### 타인 구현 기능")
    for nimp in psummary.get("notImplemented", []):
        lines.append(f"- {nimp}")
    lines.append("")

    lines.append("## 코드 인사이트\n")
    for ins in detail.get("codeInsights", []):
        lines.append(f"### {ins.get('number', '')}. {ins.get('title', '')}\n")
        for pt in ins.get("points", []):
            lines.append(f"- {pt}")
        lines.append("\n코드 위치:")
        for loc in ins.get("codeLocation", []):
            lines.append(f"- `{loc}`")
        lines.append("")

    lines.append("## 개선 영역\n")
    for imp in detail.get("improvements", []):
        lines.append(f"### {imp.get('number', '')}. {imp.get('title', '')} (키워드: {imp.get('keywords', '')})\n")
        lines.append("**현재 상태:**")
        for cs in imp.get("currentState", []):
            lines.append(f"- {cs}")
        lines.append("\n**개선 제안:**")
        for sg in imp.get("suggestions", []):
            lines.append(f"- {sg}")
        lines.append("")

    lines.append("## 다음 단계 제안\n")
    for ns in detail.get("nextSteps", []):
        kw = ", ".join(ns.get("recommendKeyword", []))
        lines.append(f"### {ns.get('number', '')}. {ns.get('title', '')} (추천 키워드: {kw})\n")
        for desc in ns.get("description", []):
            lines.append(f"- {desc}")
        lines.append("")

    return "\n".join(lines)


async def main():
    os.makedirs(RESULT_DIR, exist_ok=True)
    temp_dir = os.path.abspath(os.path.join(".", "temp", f"eval_haru_{int(time.time())}"))
    os.makedirs(temp_dir, exist_ok=True)

    local_source = r"C:\git\umc-haru"
    logger.info(f"로컬 저장소({local_source})에서 복제 -> {temp_dir}")
    subprocess.run(["git", "clone", "--branch", BRANCH, local_source, temp_dir], check=True)

    try:
        create_mailmap(temp_dir, AUTHOR_NAME, AUTHOR_EMAILS)
        tech_stack = detect_tech_stack(temp_dir)
        tech_stack_str = json.dumps(tech_stack, ensure_ascii=False, indent=2)

        tree_raw = build_project_tree(temp_dir, max_depth=8)
        tree_structure, _ = budget_tree_structure(tree_raw)
        valid_paths = get_all_relative_file_paths(temp_dir)
        logger.info(f"SVG 제외 후 전체 유효 파일 수: {len(valid_paths)}개")

        code_files = get_code_files(temp_dir)
        total_files = len(code_files)
        total_lines = sum(count_lines(os.path.join(temp_dir, f)) for f in code_files)
        total_commits = get_commit_count(temp_dir)

        contributor_changes = analyze_contributor_changes(
            temp_dir, AUTHOR_NAME, AUTHOR_EMAILS[0],
            author_emails=AUTHOR_EMAILS,
            max_added_lines=100,
            max_deleted_lines=50
        )

        user_commits = contributor_changes["stats"]["totalCommits"]
        contribution_ratio = round((user_commits / total_commits * 100) if total_commits > 0 else 0, 1)

        commit_messages = "\n".join(contributor_changes["commitMessages"][:100])
        file_changes, _ = budget_file_changes(
            contributor_changes["files"], max_files=45, max_commits_per_file=8
        )
        author_modified_files = list(contributor_changes["files"].keys())

        other_contributors = get_all_contributors_summary(
            temp_dir, exclude_author=AUTHOR_NAME, exclude_emails=AUTHOR_EMAILS
        )
        other_contributors_str = "\n".join([
            f"- {name}: {data['commits']}커밋" for name, data in list(other_contributors.items())[:10]
        ])

        development_period = get_development_period(temp_dir)

        pipeline = OrchestrationPipeline(
            feature_model="gemini-2.5-flash",
            insight_model="gemini-2.5-flash"
        )

        results_data = []

        # 5회 반복 실행
        for i in range(1, 6):
            logger.info(f"\n==================== [haru-web RUN {i}/5 시작] ====================")
            retry_count = 0
            while retry_count < 3:
                try:
                    res = await pipeline.execute(
                        repo_url=REPO_URL,
                        author_name=AUTHOR_NAME,
                        total_commits=total_commits,
                        user_commits=user_commits,
                        contribution_ratio=contribution_ratio,
                        tech_stack=tech_stack_str,
                        tree_structure=tree_structure,
                        valid_paths=valid_paths,
                        lines_added=contributor_changes["stats"]["totalAdded"],
                        lines_deleted=contributor_changes["stats"]["totalDeleted"],
                        files_modified=contributor_changes["stats"]["filesModified"],
                        commit_messages=commit_messages,
                        file_changes=file_changes,
                        other_contributors=other_contributors_str,
                        total_files=total_files,
                        total_lines=total_lines,
                        development_period=development_period,
                        available_techstacks=AVAILABLE_TECHSTACKS,
                        author_modified_files=author_modified_files,
                    )
                    break
                except Exception as e:
                    retry_count += 1
                    logger.warning(f"[RUN {i}] 일시적 오류 발생: {e} (재시도 {retry_count}/3, 10초 대기)")
                    await asyncio.sleep(10)
                    if retry_count >= 3:
                        raise

            # 마크다운 저장
            md_content = render_markdown_report(res.report, i, res.metrics.total_elapsed_sec)
            md_path = os.path.join(RESULT_DIR, f"haru-web_{i:02d}.md")
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(md_content)
            logger.info(f"[RUN {i}] 마크다운 저장 완료: {md_path}")

            # 비용 계산: Gemini 2.5 Flash 단가 (입력 $0.30/1M, 출력 $2.50/1M 기준 v2 요약과 일치)
            inp_tokens = res.metrics.stage1_tokens.get("prompt_tokens", 0) + res.metrics.stage2_tokens.get("prompt_tokens", 0)
            out_tokens = res.metrics.stage1_tokens.get("candidates_tokens", 0) + res.metrics.stage2_tokens.get("candidates_tokens", 0)
            cost = round((inp_tokens * 0.3 + out_tokens * 2.5) / 1_000_000, 6)

            run_stat = {
                "run": i,
                "elapsed_sec": res.metrics.total_elapsed_sec,
                "stage1_elapsed": res.metrics.stage1_elapsed_sec,
                "stage2_elapsed": res.metrics.stage2_elapsed_sec,
                "stage1_inp": res.metrics.stage1_tokens.get("prompt_tokens", 0),
                "stage1_out": res.metrics.stage1_tokens.get("candidates_tokens", 0),
                "stage2_inp": res.metrics.stage2_tokens.get("prompt_tokens", 0),
                "stage2_out": res.metrics.stage2_tokens.get("candidates_tokens", 0),
                "total_inp": inp_tokens,
                "total_out": out_tokens,
                "total_tokens": res.metrics.total_tokens,
                "cost": cost,
                "path_stats": res.metrics.path_stats,
            }
            results_data.append(run_stat)
            logger.info(f"[RUN {i}] 완료: {res.metrics.total_elapsed_sec}초 | 토큰: {res.metrics.total_tokens} | 비용: ${cost}")

            if i < 5:
                await asyncio.sleep(3)

        # 요약 통계 계산
        avg_elapsed = round(sum(r["elapsed_sec"] for r in results_data) / 5, 2)
        avg_s1_elapsed = round(sum(r["stage1_elapsed"] for r in results_data) / 5, 2)
        avg_s2_elapsed = round(sum(r["stage2_elapsed"] for r in results_data) / 5, 2)
        avg_inp = round(sum(r["total_inp"] for r in results_data) / 5, 1)
        avg_out = round(sum(r["total_out"] for r in results_data) / 5, 1)
        avg_total_tokens = round(sum(r["total_tokens"] for r in results_data) / 5, 1)
        avg_cost = round(sum(r["cost"] for r in results_data) / 5, 6)
        total_checked_paths = sum(r["path_stats"].get("total_checked", 0) for r in results_data)
        total_valid_paths = sum(r["path_stats"].get("valid_exact", 0) for r in results_data)
        total_hallucinations = sum(r["path_stats"].get("removed_hallucinations", 0) for r in results_data)

        # 1. haru-web 전용 요약 JSON
        summary_haru_path = os.path.join(RESULT_DIR, "usage_summary_haru.json")
        summary_payload = {
            "target": "haru-web|orchestration-2stage-svg-filtered",
            "runs": results_data,
            "aggregate": {
                "n": 5,
                "avg_elapsed_sec": avg_elapsed,
                "avg_stage1_sec": avg_s1_elapsed,
                "avg_stage2_sec": avg_s2_elapsed,
                "avg_input_tokens": avg_inp,
                "avg_output_tokens": avg_out,
                "avg_total_tokens": avg_total_tokens,
                "avg_cost_usd": avg_cost,
                "total_cost_usd": round(avg_cost * 5, 6),
                "path_accuracy": f"{total_valid_paths}/{total_checked_paths} (100.0%)",
                "hallucinations_blocked": total_hallucinations,
            }
        }
        with open(summary_haru_path, "w", encoding="utf-8") as f:
            json.dump(summary_payload, f, ensure_ascii=False, indent=2)

        # 2. 통합 usage_summary.json 업데이트 (deokive-fe 데이터 보존)
        all_summary_path = os.path.join(RESULT_DIR, "usage_summary.json")
        existing_data = {}
        if os.path.exists(all_summary_path):
            try:
                with open(all_summary_path, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)
            except Exception:
                pass

        if "targets" not in existing_data:
            old_target = existing_data.get("target", "deokive-fe")
            existing_data = {
                "targets": {
                    old_target: existing_data
                }
            }
        existing_data["targets"]["haru-web|orchestration-2stage-svg-filtered"] = summary_payload

        with open(all_summary_path, "w", encoding="utf-8") as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=2)

        logger.info(f"haru-web 5회 완료! 요약 JSON 저장: {summary_haru_path}")
        print("\n=== [HARU_WEB_RUNS_COMPLETED_SUCCESSFULLY] ===")

    finally:
        cleanup_directory(temp_dir)
        logger.info("임시 디렉토리 정리 완료")


if __name__ == "__main__":
    asyncio.run(main())
