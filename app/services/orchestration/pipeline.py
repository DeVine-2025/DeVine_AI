import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from app.services.orchestration.agents.feature_agent import FeatureAgent
from app.services.orchestration.agents.insight_agent import InsightAgent

logger = logging.getLogger(__name__)


@dataclass
class OrchestrationResult:
    report: dict
    stage1_output: dict
    stage1_usage: dict
    stage2_usage: dict
    total_tokens: int
    elapsed_seconds: float
    path_stats: dict = field(default_factory=dict)


class OrchestrationPipeline:
    """Stage 1 (Feature Extraction) -> Stage 2 (Insight Synthesis) 2단계 오케스트레이션 파이프라인"""

    def __init__(
        self,
        feature_model: str = "gemini-2.5-flash",
        insight_model: str = "gemini-2.5-flash",
    ):
        self.feature_agent = FeatureAgent(model_name=feature_model)
        self.insight_agent = InsightAgent(model_name=insight_model)

    async def execute(
        self,
        repo_url: str,
        author_name: str,
        total_commits: int,
        user_commits: int,
        contribution_ratio: float,
        tech_stack: str,
        tree_structure: str,
        lines_added: int,
        lines_deleted: int,
        files_modified: int,
        commit_messages: str,
        file_changes: str,
        other_contributors: str,
        total_files: int,
        total_lines: int,
        development_period: str,
        available_techstacks: list = None,
        valid_paths: Optional[set] = None,
        author_modified_files: Optional[list] = None,
    ) -> OrchestrationResult:
        start_time = time.time()
        logger.info(f"[OrchestrationPipeline] 파이프라인 시작: author={author_name}, repo={repo_url}")

        # Stage 1: Feature & Code Extraction
        stage1_res = await self.feature_agent.execute(
            repo_url=repo_url,
            author_name=author_name,
            total_commits=total_commits,
            user_commits=user_commits,
            contribution_ratio=contribution_ratio,
            tech_stack=tech_stack,
            tree_structure=tree_structure,
            lines_added=lines_added,
            lines_deleted=lines_deleted,
            files_modified=files_modified,
            commit_messages=commit_messages,
            file_changes=file_changes,
            other_contributors=other_contributors,
        )
        stage1_output = stage1_res["data"]

        # Stage 2: Insight Synthesis & Final Report Generation
        stage2_res = await self.insight_agent.execute(
            repo_url=repo_url,
            author_name=author_name,
            total_commits=total_commits,
            user_commits=user_commits,
            contribution_ratio=contribution_ratio,
            total_files=total_files,
            total_lines=total_lines,
            development_period=development_period,
            stage1_output=stage1_output,
            available_techstacks=available_techstacks,
        )
        final_report = stage2_res["data"]
        elapsed = time.time() - start_time

        stage1_tokens = stage1_res["token_usage"]["total_token_count"]
        stage2_tokens = stage2_res["token_usage"]["total_token_count"]
        total_tokens = stage1_tokens + stage2_tokens

        logger.info(
            f"[OrchestrationPipeline] 파이프라인 완료 ({elapsed:.1f}초). "
            f"Stage 1 토큰: {stage1_tokens}, Stage 2 토큰: {stage2_tokens}, 총 토큰: {total_tokens}"
        )

        return OrchestrationResult(
            report=final_report,
            stage1_output=stage1_output,
            stage1_usage=stage1_res["token_usage"],
            stage2_usage=stage2_res["token_usage"],
            total_tokens=total_tokens,
            elapsed_seconds=elapsed,
            path_stats={},
        )
