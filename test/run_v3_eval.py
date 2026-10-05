"""
v3 종합 벤치마크 평가 러너: deokive-fe, haru-web, devine_deploy
적용 기능 (v3 고도화):
1. AST & Code Outliner: 거대 단일 파일에서 함수/클래스 시그니처 우선 보존 및 본문 압축
2. Dedicated Infra Budget: 비즈니스 diff와 인프라 diff 분리 배분 (인프라 기여 독립 보장)
3. Change Scale & Migration Metadata: 전체 수정 규모 및 전역 리팩토링 맥락 명시
4. Strict Bounds & 안전 가드 유지 (경로 15~25개, 타임아웃, 예산 사전 검사)

결과 저장: C:\\git\\devine\\result\\v3
"""

import os
import sys
import asyncio
import json
import time
import logging
import subprocess
from typing import Dict, Any, List

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
from app.utils.diff_budgeter import (
    budget_file_changes_v3,
    budget_tree_structure,
)
from app.utils.metadata_extractor import extract_change_metadata
from app.services.orchestration.pipeline import OrchestrationPipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("eval_v3")

RESULT_V3_DIR = r"C:\git\devine\result\v3"
os.makedirs(RESULT_V3_DIR, exist_ok=True)

AVAILABLE_TECHSTACKS = [
    "TYPESCRIPT", "JAVASCRIPT", "REACT", "NEXTJS", "VUE", "TAILWINDCSS",
    "REDUX", "ZUSTAND", "REACTQUERY", "AXIOS", "HTML", "CSS", "NODEJS",
    "PYTHON", "JAVA", "SPRINGBOOT", "POSTGRESQL", "MYSQL", "DOCKER", "AWS",
    "TERRAFORM", "OCI", "KUBERNETES", "NGINX"
]


def render_markdown_report_v3(
    report: dict,
    repo_tag: str,
    repo_url: str,
    branch: str,
    commit_hash: str,
    author_name: str,
    run_idx: int,
    elapsed_sec: float
) -> str:
    main = report.get("main", {})
    detail = report.get("detail", {})
    techstacks = report.get("techstacks", [])
    migration_meta = detail.get("migrationMeta", {})
    infra_work = detail.get("infraAndDevOps", {})

    lines = []
    lines.append(f"# {repo_tag} 리포트 #{run_idx:02d} (v3)\n")
    lines.append(f"- 레포: {repo_url} (`{branch}` @ `{commit_hash}`)")
    lines.append(f"- 분석 대상: {author_name}")
    lines.append(f"- 모델: gemini-2.5-flash (2-Stage Orchestration v3 + AST Outliner + Infra Guard + Metadata)")
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
        for tag in impl.get("tags", []):
            lines.append(f"- {tag}")
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
    lines.append(f"# Detail 리포트: {detail.get('reportTitle', repo_tag)}\n")
    lines.append(f"_{detail.get('reportSubtitle', '프로젝트 상세 분석 리포트')}_\n")

    # v3 Metadata Section
    if migration_meta:
        lines.append("## 프로젝트 변경 규모 및 마이그레이션 메타데이터 (v3)\n")
        lines.append(f"- **총 수정 파일 수**: {migration_meta.get('totalFilesModified', 0)}개")
        lines.append(f"- **대규모 리팩토링/전역 변경**: {'예 (Large-scale)' if migration_meta.get('isLargeScale') else '아니오 (일반 기능 개발)'}")
        lines.append(f"- **범위 및 선별 맥락**: {migration_meta.get('scopeDescription', '')}\n")

    # v3 Infra & DevOps Section
    if infra_work and infra_work.get("hasInfraWork"):
        lines.append("## 인프라 및 DevOps 엔지니어링 기여 (v3 Dedicated)\n")
        lines.append(f"- **사용 기술**: {', '.join(infra_work.get('technologies', []))}")
        lines.append(f"- **기여 요약**: {infra_work.get('summary', '')}")
        lines.append("- **주요 설정 파일**:")
        for kf in infra_work.get("keyFiles", []):
            lines.append(f"  - `{kf}`")
        lines.append("")

    p_overview = detail.get("projectOverview", {})
    lines.append("## 프로젝트 개요\n")
    lines.append(f"{p_overview.get('purpose', '')}\n")
    lines.append("**기술 스택**\n")
    for ts in p_overview.get("techStack", []):
        lines.append(f"- **{ts.get('title', '')}**: {ts.get('content', '')}")
    lines.append("")

    pscale = p_overview.get("projectScale", {})
    lines.append("**규모**\n")
    lines.append(f"- 주요 코드 파일: {pscale.get('mainCodeFiles', 0)}")
    lines.append(f"- 총 코드 라인: {pscale.get('totalCodeLines', 0)}")
    lines.append(f"- 개발 기간: {pscale.get('developmentPeriod', '')}")
    lines.append(f"- 아키텍처: {pscale.get('architecturePattern', '')}\n")

    lines.append("## 구현 기능\n")
    for cat in detail.get("implementedFeatures", []):
        lines.append(f"### {cat.get('categoryNumber', '')}. {cat.get('category', '')}\n")
        for f in cat.get("features", []):
            lines.append(f"#### {f.get('name', '')}\n")
            lines.append("구현:")
            for imp in f.get("implementation", []):
                lines.append(f"- {imp}")
            lines.append("\n세부:")
            for det in f.get("details", []):
                lines.append(f"- {det}")
            lines.append("\n코드 위치:")
            for loc in f.get("codeLocation", []):
                lines.append(f"- `{loc}`")
            lines.append("")

    psum = detail.get("projectSummary", {})
    lines.append("## 프로젝트 요약\n")
    lines.append("### 본인 구현 기능")
    for my in psum.get("implemented", []):
        lines.append(f"- {my}")
    lines.append("\n### 타인 구현 기능")
    for other in psum.get("notImplemented", []):
        lines.append(f"- {other}")
    lines.append("")

    lines.append("## 코드 인사이트\n")
    for i, ins in enumerate(detail.get("codeInsights", []), 1):
        lines.append(f"### {i}. {ins.get('title', '')}\n")
        for det in ins.get("details", []):
            lines.append(f"- {det}")
        lines.append("")

    return "\n".join(lines)


async def run_single_eval_v3(
    target_name: str,
    repo_url: str,
    local_source: str,
    author_name: str,
    author_emails: list,
    branch: str = "develop",
    run_idx: int = 1,
) -> dict:
    logger.info(f"=== [{target_name} v3 #{run_idx}] 분석 시작 ===")
    start_time = time.time()

    temp_dir = os.path.abspath(os.path.join(DEVINE_AI_DIR, "temp", f"eval_v3_{target_name}_{int(time.time())}"))
    os.makedirs(temp_dir, exist_ok=True)
    logger.info(f"[{target_name}] 로컬 소스({local_source})에서 복제 -> {temp_dir}")
    subprocess.run(["git", "clone", "--branch", branch, local_source, temp_dir], check=True, capture_output=True)

    try:
        create_mailmap(temp_dir, author_name, author_emails)
        total_commits = get_commit_count(temp_dir)
        tree_raw = build_project_tree(temp_dir, max_depth=8)
        tree_structure, _ = budget_tree_structure(tree_raw)
        valid_paths = get_all_relative_file_paths(temp_dir)

        code_files = get_code_files(temp_dir)
        total_files = len(code_files)
        total_lines = sum(count_lines(os.path.join(temp_dir, f)) for f in code_files)
        tech_stack = detect_tech_stack(temp_dir)
        tech_stack_str = json.dumps(tech_stack, ensure_ascii=False, indent=2)

        contributor_changes = analyze_contributor_changes(
            temp_dir, author_name, author_emails[0],
            author_emails=author_emails,
            max_added_lines=3000,
            max_deleted_lines=3000
        )

        user_commits = contributor_changes["stats"]["totalCommits"]
        contribution_ratio = round((user_commits / total_commits * 100) if total_commits > 0 else 0, 1)

        commit_messages = "\n".join(contributor_changes["commitMessages"][:35])

        # v3 메타데이터 추출
        change_meta = extract_change_metadata(contributor_changes["files"], contributor_changes["stats"])

        # v3 이원화 비례 절단 및 AST 압축
        business_diff, infra_diff, is_truncated = budget_file_changes_v3(contributor_changes["files"])

        author_modified_files = list(contributor_changes["files"].keys())

        other_contributors = get_all_contributors_summary(temp_dir, exclude_author=author_name, exclude_emails=author_emails)
        other_contributors_str = "\n".join([f"- {name}: {data['commits']}커밋" for name, data in list(other_contributors.items())[:10]])

        development_period = get_development_period(temp_dir)

        # HEAD 커밋 해시
        try:
            rev = subprocess.run(["git", "-C", temp_dir, "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True)
            commit_hash = rev.stdout.strip()
        except Exception:
            commit_hash = "HEAD"

        pipeline = OrchestrationPipeline(feature_model="gemini-2.5-flash", insight_model="gemini-2.5-flash")

        orch_result = await pipeline.execute(
            repo_url=repo_url,
            author_name=author_name,
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
            file_changes=business_diff,
            other_contributors=other_contributors_str,
            total_files=total_files,
            total_lines=total_lines,
            development_period=development_period,
            available_techstacks=AVAILABLE_TECHSTACKS,
            author_modified_files=author_modified_files,
            change_metadata=change_meta["summary_text"],
            infra_changes=infra_diff,
        )

        elapsed_sec = round(time.time() - start_time, 2)
        report = orch_result.report
        metrics = orch_result.metrics

        # 비용 계산
        inp_tokens = metrics.stage1_tokens.get("prompt_tokens", 0) + metrics.stage2_tokens.get("prompt_tokens", 0)
        out_tokens = metrics.stage1_tokens.get("candidates_tokens", 0) + metrics.stage2_tokens.get("candidates_tokens", 0)
        cost = (inp_tokens * 0.30 + out_tokens * 2.50) / 1_000_000

        # 마크다운 리포트 생성 및 저장
        md_content = render_markdown_report_v3(
            report=report,
            repo_tag=target_name,
            repo_url=repo_url,
            branch=branch,
            commit_hash=commit_hash,
            author_name=author_name,
            run_idx=run_idx,
            elapsed_sec=elapsed_sec
        )

        out_file = os.path.join(RESULT_V3_DIR, f"{target_name}_{run_idx:02d}.md")
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(md_content)

        logger.info(f"[{target_name} v3 #{run_idx}] 리포트 저장 완료: {out_file}")

        return {
            "target": target_name,
            "run": run_idx,
            "elapsed_sec": elapsed_sec,
            "stage1_elapsed": metrics.stage1_elapsed_sec,
            "stage2_elapsed": metrics.stage2_elapsed_sec,
            "stage1_inp": metrics.stage1_tokens.get("prompt_tokens", 0),
            "stage1_out": metrics.stage1_tokens.get("candidates_tokens", 0),
            "stage2_inp": metrics.stage2_tokens.get("prompt_tokens", 0),
            "stage2_out": metrics.stage2_tokens.get("candidates_tokens", 0),
            "total_inp": inp_tokens,
            "total_out": out_tokens,
            "total_tokens": metrics.total_tokens,
            "cost": round(cost, 6),
            "path_stats": metrics.path_stats,
            "has_infra": bool(report.get("detail", {}).get("infraAndDevOps", {}).get("hasInfraWork")),
            "is_large_scale": bool(report.get("detail", {}).get("migrationMeta", {}).get("isLargeScale")),
        }
    finally:
        cleanup_directory(temp_dir)


async def main():
    targets = [
        {
            "name": "deokive-fe",
            "url": "https://github.com/Deokive/FE.git",
            "local_source": r"C:\git\devine\Devine_ai\temp\git-Deokive-FE-641703e7",
            "author_name": "strfunctionk",
            "author_emails": ["strfunctionk@gmail.com", "jh.lee.6738@gmail.com"],
            "branch": "develop",
        },
        {
            "name": "haru-web",
            "url": "https://github.com/HaRu-Developers/haru-web.git",
            "local_source": r"C:\git\devine\Devine_ai\temp\git-HaRu-Developers-haru-web-75eb4b46",
            "author_name": "strfunctionk",
            "author_emails": ["strfunctionk@gmail.com", "jh.lee.6738@gmail.com"],
            "branch": "develop",
        },
        {
            "name": "devine-deploy",
            "url": "https://github.com/DeVine-2025/Devine_Deploy.git",
            "local_source": r"C:\git\devine\devine_deploy",
            "author_name": "heo",
            "author_emails": ["qetyop9762@gmail.com"],
            "branch": "main",
        }
    ]

    all_results = []
    for t in targets:
        logger.info(f"\n=======================================================")
        logger.info(f"  Target: {t['name']} (URL: {t['url']}, Author: {t['author_name']})")
        logger.info(f"=======================================================\n")
        res = await run_single_eval_v3(
            target_name=t["name"],
            repo_url=t["url"],
            local_source=t["local_source"],
            author_name=t["author_name"],
            author_emails=t["author_emails"],
            branch=t["branch"],
            run_idx=1,
        )
        all_results.append(res)
        await asyncio.sleep(2)

    summary_file = os.path.join(RESULT_V3_DIR, "v3_benchmark_summary.json")
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    logger.info(f"\n=== [전체 v3 벤치마크 완료] 요약 저장: {summary_file} ===")
    for r in all_results:
        logger.info(
            f"[{r['target']}] 소요: {r['elapsed_sec']}s, 입력토큰: {r['total_inp']:,}, "
            f"비용: ${r['cost']}, 인프라포착: {r['has_infra']}, 마이그레이션감지: {r['is_large_scale']}"
        )


if __name__ == "__main__":
    asyncio.run(main())
