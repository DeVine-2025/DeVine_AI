import time
import logging
from typing import Dict, Any, List, Set, Optional
from dataclasses import dataclass, field

from app.services.orchestration.agents.feature_agent import FeatureAgent
from app.services.orchestration.agents.insight_agent import InsightAgent
from app.services.orchestration.validators.path_validator import PathValidator
from app.utils.diff_budgeter import budget_tree_structure, DEFAULT_MAX_DIFF_CHARS, DEFAULT_MAX_TREE_CHARS

logger = logging.getLogger(__name__)


@dataclass
class OrchestrationMetrics:
    total_elapsed_sec: float = 0.0
    stage1_elapsed_sec: float = 0.0
    stage2_elapsed_sec: float = 0.0
    stage1_tokens: Dict[str, int] = field(default_factory=dict)
    stage2_tokens: Dict[str, int] = field(default_factory=dict)
    total_tokens: int = 0
    path_stats: Dict[str, int] = field(default_factory=dict)


@dataclass
class OrchestrationResult:
    report: Dict[str, Any]
    metrics: OrchestrationMetrics


class OrchestrationPipeline:
    """
    2-Stage Sequential Chaining + Deterministic Guardrail Pipeline
    Stage 1: FeatureAgent (Fact & Code extraction)
      ↓
    Guardrail: PathValidator (Deterministic zero-token verification)
      ↓
    Stage 2: InsightAgent (Evaluation & Synthesis)
      ↓
    Assembler (Final report synthesis compatible with Spring Backend)
    """

    def __init__(
        self,
        feature_model: str = "gemini-2.5-flash",
        insight_model: str = "gemini-2.5-flash",
        max_budget_usd: float = 0.08,
    ):
        self.feature_agent = FeatureAgent(model_name=feature_model)
        self.insight_agent = InsightAgent(model_name=insight_model)
        self.max_budget_usd = max_budget_usd

    async def execute(
        self,
        repo_url: str,
        author_name: str,
        total_commits: int,
        user_commits: int,
        contribution_ratio: float,
        tech_stack: str,
        tree_structure: str,
        valid_paths: Set[str],
        lines_added: int,
        lines_deleted: int,
        files_modified: int,
        commit_messages: str,
        file_changes: str,
        other_contributors: str,
        total_files: int,
        total_lines: int,
        development_period: str,
        available_techstacks: Optional[List[str]] = None,
        author_modified_files: Optional[List[str]] = None,
    ) -> OrchestrationResult:
        start_time = time.time()
        metrics = OrchestrationMetrics()

        logger.info(f"=== [OrchestrationPipeline] 파이프라인 시작 (Repo: {repo_url}, Author: {author_name}) ===")

        # -------------------------------------------------------------
        # 0. Diff & Tree Budgeter (비례 절단 및 상한선 적용 - umc11th 벤치마킹)
        # -------------------------------------------------------------
        budgeted_tree, tree_truncated = budget_tree_structure(tree_structure)
        
        # file_changes 문자열 비례 절단 검사
        if len(file_changes) > DEFAULT_MAX_DIFF_CHARS:
            logger.info(
                f"[OrchestrationPipeline] file_changes 길이({len(file_changes):,}자)가 상한({DEFAULT_MAX_DIFF_CHARS:,}자) 초과 -> 비례 절단 적용"
            )
            raw_blocks = file_changes.split("\n=== ")
            file_blocks = [("=== " + b if not b.startswith("===") else b) for b in raw_blocks if b.strip()]
            total_len = sum(len(b) for b in file_blocks)
            ratio = DEFAULT_MAX_DIFF_CHARS / total_len
            truncated_blocks = []
            for b in file_blocks:
                keep = max(350, int(len(b) * ratio))
                if len(b) > keep:
                    truncated_blocks.append(f"{b[:keep]}\n…(파일 변경 분량 상한으로 이하 생략)\n")
                else:
                    truncated_blocks.append(b)
            budgeted_file_changes = "\n".join(truncated_blocks)
        else:
            budgeted_file_changes = file_changes

        # Pre-flight Worst-Case 예산 사전 검사 (호출 전 차단/모니터링)
        total_prompt_chars = (
            len(repo_url) + len(tech_stack) + len(budgeted_tree) +
            len(commit_messages) + len(budgeted_file_changes) + len(other_contributors)
        )
        est_tokens = int(total_prompt_chars * 0.35)
        worst_case_cost = round((est_tokens * 0.30 + 8192 * 2.50) / 1_000_000, 4)
        logger.info(
            f"[OrchestrationPipeline] 사전 예산 추정: 예상 입력 ~{est_tokens:,} tok, "
            f"최악 비용 ${worst_case_cost} (상한: ${self.max_budget_usd})"
        )
        if worst_case_cost > self.max_budget_usd:
            logger.warning(f"[OrchestrationPipeline] 사전 추정 비용(${worst_case_cost})이 예산 상한(${self.max_budget_usd})에 근접하거나 초과함")

        # -------------------------------------------------------------
        # Stage 1: Feature Agent (Fact-finding & Code locations)
        # -------------------------------------------------------------
        stage1_start = time.time()
        stage1_raw, stage1_tokens = await self.feature_agent.analyze(
            repo_url=repo_url,
            author_name=author_name,
            total_commits=total_commits,
            user_commits=user_commits,
            contribution_ratio=contribution_ratio,
            tech_stack=tech_stack,
            tree_structure=budgeted_tree,
            lines_added=lines_added,
            lines_deleted=lines_deleted,
            files_modified=files_modified,
            commit_messages=commit_messages,
            file_changes=budgeted_file_changes,
            other_contributors=other_contributors,
            available_techstacks=available_techstacks,
        )
        metrics.stage1_elapsed_sec = round(time.time() - stage1_start, 2)
        metrics.stage1_tokens = stage1_tokens

        # -------------------------------------------------------------
        # Guardrail: Deterministic Path Validation
        # -------------------------------------------------------------
        validator = PathValidator(valid_paths=valid_paths)
        validated_stage1, path_stats = validator.validate_feature_analysis(
            feature_result=stage1_raw,
            fallback_files=author_modified_files
        )
        metrics.path_stats = path_stats
        logger.info(f"[OrchestrationPipeline] 가드레일 완료: {path_stats}")

        # -------------------------------------------------------------
        # Stage 2: Insight Agent (Evaluation & High-level insights)
        # -------------------------------------------------------------
        stage2_start = time.time()
        stage2_raw, stage2_tokens = await self.insight_agent.analyze(
            repo_url=repo_url,
            author_name=author_name,
            total_files=total_files,
            total_lines=total_lines,
            development_period=development_period,
            verified_feature_result=validated_stage1,
        )
        metrics.stage2_elapsed_sec = round(time.time() - stage2_start, 2)
        metrics.stage2_tokens = stage2_tokens

        # -------------------------------------------------------------
        # Assembler: Merge into Spring-compatible Report Schema
        # -------------------------------------------------------------
        final_report = self._assemble_report(
            repo_url=repo_url,
            stage1=validated_stage1,
            stage2=stage2_raw,
        )

        total_elapsed = round(time.time() - start_time, 2)
        metrics.total_elapsed_sec = total_elapsed
        metrics.total_tokens = (
            stage1_tokens.get("total_tokens", 0) + stage2_tokens.get("total_tokens", 0)
        )

        logger.info(
            f"=== [OrchestrationPipeline] 파이프라인 종료 - 총 소요: {total_elapsed}초, "
            f"총 토큰: {metrics.total_tokens}, 경로 환각 차단: {path_stats.get('removed_hallucinations', 0)}건 ==="
        )

        return OrchestrationResult(report=final_report, metrics=metrics)

    def _assemble_report(
        self,
        repo_url: str,
        stage1: Dict[str, Any],
        stage2: Dict[str, Any],
    ) -> Dict[str, Any]:
        """기존 Spring Boot 백엔드가 기대하는 JSON 포맷으로 조립"""
        repo_name = repo_url.rstrip("/").split("/")[-1]
        if repo_name.endswith(".git"):
            repo_name = repo_name[:-4]

        main_section = {
            "overview": stage2.get("overview", {}),
            "projectInfo": stage2.get("projectInfo", {}),
            "keyImplementations": stage1.get("keyImplementations", []),
            "aiEvaluation": stage2.get("aiEvaluation", []),
            "recommendations": stage2.get("recommendations", []),
        }

        # 프로젝트명 기본 보정
        if not main_section["projectInfo"].get("projectName"):
            main_section["projectInfo"]["projectName"] = repo_name

        detail_section = {
            "reportTitle": repo_name,
            "reportSubtitle": "프로젝트 상세 분석 리포트",
            "projectOverview": stage2.get("projectOverview", {}),
            "implementedFeatures": stage1.get("implementedFeatures", []),
            "projectSummary": stage1.get("projectSummary", {}),
            "codeInsights": stage1.get("codeInsights", []),
            "improvements": stage2.get("improvements", []),
            "nextSteps": stage2.get("nextSteps", []),
        }

        return {
            "techstacks": stage1.get("techstacks", []),
            "main": main_section,
            "detail": detail_section,
        }
