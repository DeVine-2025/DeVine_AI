"""
오케스트레이션 직접 구현(PoC) 평가 및 비교 실행 스크립트
대상: deokive-fe (https://github.com/Deokive/FE.git)
분석 대상: strfunctionk
"""

import os
import sys
import asyncio
import json
import time
import logging

# Devine_ai 경로 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.git_service import (
    clone_repository,
    cleanup_directory,
    create_mailmap,
    get_commit_count,
    get_commit_history,
    analyze_contributor_changes,
    get_all_contributors_summary,
    get_development_period,
)
from app.utils.file_reader import get_code_files, count_lines, count_test_files
from app.utils.tech_detector import detect_tech_stack
from app.utils.tree_builder import build_project_tree, get_all_relative_file_paths
from app.services.orchestration.pipeline import OrchestrationPipeline
from app.configs.settings import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("eval_runner")

REPO_URL = "https://github.com/Deokive/FE.git"
BRANCH = "develop"
AUTHOR_NAME = "strfunctionk"
AUTHOR_EMAIL = "strfunctionk@gmail.com"
AUTHOR_EMAILS = [
    "strfunctionk@gmail.com",
    "strfunctionk@users.noreply.github.com",
    "85854384+strfunctionk@users.noreply.github.com"
]

AVAILABLE_TECHSTACKS = [
    "TYPESCRIPT", "JAVASCRIPT", "REACT", "NEXTJS", "VUE", "TAILWINDCSS",
    "REDUX", "ZUSTAND", "REACTQUERY", "AXIOS", "HTML", "CSS", "NODEJS",
    "PYTHON", "JAVA", "SPRINGBOOT", "POSTGRESQL", "MYSQL", "DOCKER", "AWS"
]


async def run_eval():
    logger.info(f"=== [EVAL] {REPO_URL} ({BRANCH}) 클론 시작 ===")
    start_time = time.time()
    
    # 1. Local Clone & Checkout develop branch
    unique_id = str(int(time.time()))[-6:]
    temp_dir = os.path.abspath(os.path.join(".", "temp", f"eval-{unique_id}"))
    os.makedirs(temp_dir, exist_ok=True)
    
    local_source = r"C:\git\Deokive"
    logger.info(f"로컬 저장소({local_source})에서 복제 -> {temp_dir}")
    import subprocess
    subprocess.run(["git", "clone", "--branch", BRANCH, local_source, temp_dir], check=True)
    dir_path = temp_dir
    logger.info(f"로컬 클론 및 브랜치({BRANCH}) 준비 완료 ({dir_path})")

    try:
        # 2. Mailmap & Git stats
        create_mailmap(dir_path, AUTHOR_NAME, AUTHOR_EMAILS)
        tech_stack = detect_tech_stack(dir_path)
        tech_stack_str = json.dumps(tech_stack, ensure_ascii=False, indent=2)

        tree_structure = build_project_tree(dir_path, max_depth=15)
        valid_paths = get_all_relative_file_paths(dir_path)
        logger.info(f"전체 유효 파일 수: {len(valid_paths)}개")

        code_files = get_code_files(dir_path)
        total_files = len(code_files)
        total_lines = sum(count_lines(os.path.join(dir_path, f)) for f in code_files)
        total_commits = get_commit_count(dir_path)

        contributor_changes = analyze_contributor_changes(
            dir_path, AUTHOR_NAME, AUTHOR_EMAIL,
            author_emails=AUTHOR_EMAILS,
            max_added_lines=100,
            max_deleted_lines=50
        )

        user_commits = contributor_changes["stats"]["totalCommits"]
        contribution_ratio = round((user_commits / total_commits * 100) if total_commits > 0 else 0, 1)

        commit_messages = "\n".join(contributor_changes["commitMessages"][:100])
        
        from app.services.analyzer_service import analyzer_service
        file_changes = analyzer_service._format_file_changes(
            contributor_changes["files"],
            max_files=80,
            max_commits_per_file=10
        )
        author_modified_files = list(contributor_changes["files"].keys())

        other_contributors = get_all_contributors_summary(
            dir_path, exclude_author=AUTHOR_NAME, exclude_emails=AUTHOR_EMAILS
        )
        other_contributors_str = "\n".join([
            f"- {name}: {data['commits']}커밋" for name, data in list(other_contributors.items())[:10]
        ])

        development_period = get_development_period(dir_path)

        # 3. 오케스트레이션 파이프라인 실행
        logger.info("=== [EVAL] 2단계 오케스트레이션 파이프라인 실행 시작 ===")
        pipeline = OrchestrationPipeline(
            feature_model="gemini-2.5-flash",
            insight_model="gemini-2.5-flash"
        )

        result = await pipeline.execute(
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

        # 4. 결과 저장
        output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "docs", "poc_eval_result"))
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, "deokive-fe_orchestration_result.json")

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump({
                "metrics": {
                    "total_elapsed_sec": result.metrics.total_elapsed_sec,
                    "stage1_elapsed_sec": result.metrics.stage1_elapsed_sec,
                    "stage2_elapsed_sec": result.metrics.stage2_elapsed_sec,
                    "stage1_tokens": result.metrics.stage1_tokens,
                    "stage2_tokens": result.metrics.stage2_tokens,
                    "total_tokens": result.metrics.total_tokens,
                    "path_stats": result.metrics.path_stats,
                },
                "report": result.report
            }, f, ensure_ascii=False, indent=2)

        logger.info(f"=== [EVAL] 성공! 결과 저장됨: {output_file} ===")
        print(f"\n[EVAL_SUCCESS] 결과 파일: {output_file}")
        print(f"총 소요 시간: {result.metrics.total_elapsed_sec}초")
        print(f"Stage 1 소요: {result.metrics.stage1_elapsed_sec}초, Stage 2 소요: {result.metrics.stage2_elapsed_sec}초")
        print(f"총 토큰: {result.metrics.total_tokens}")
        print(f"경로 가드레일 통계: {result.metrics.path_stats}")

    finally:
        cleanup_directory(dir_path)
        logger.info(f"임시 디렉토리 정리 완료: {dir_path}")


if __name__ == "__main__":
    asyncio.run(run_eval())
