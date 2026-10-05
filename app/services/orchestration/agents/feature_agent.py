import asyncio
import logging
import json
from google import genai
from google.genai import types, errors
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from app.configs.settings import settings
from app.services.orchestration.schemas.feature_schema import FEATURE_SCHEMA
from app.services.orchestration.prompts.feature_prompt import get_feature_analysis_prompt
from app.services.gemini_service import gemini_service
from app.errors.exceptions import GeminiException

logger = logging.getLogger(__name__)

client = genai.Client(api_key=settings.gemini_api_key)


class FeatureAgent:
    """
    Stage 1: 기능 분석 에이전트 (Fact & Code Analysis)
    Git diff, 커밋 로그, 파일 트리를 분석하여 실제 구현 기능, 기술 스택, 파일 위치를 사실 기반으로 추출합니다.
    """

    SYSTEM_INSTRUCTION = (
        "You are an expert technical code auditor. "
        "Strictly analyze only code contributions actually made by the author. "
        "Do not invent non-existent features or exaggerate contributions. "
        "Write all natural language descriptions in Korean (한국어)."
    )

    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self.model_name = model_name

    STAGE1_TIMEOUT_SECONDS = 75

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(errors.ServerError),
        reraise=True,
    )
    async def _generate_content(self, prompt: str) -> tuple[dict, object]:
        try:
            response = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=self.SYSTEM_INSTRUCTION,
                        response_mime_type="application/json",
                        response_schema=FEATURE_SCHEMA,
                    ),
                ),
                timeout=self.STAGE1_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError as e:
            logger.error(f"[FeatureAgent] Stage 1 타임아웃 발생 ({self.STAGE1_TIMEOUT_SECONDS}초 초과)")
            raise GeminiException(f"Stage 1 LLM 호출 시간 초과 ({self.STAGE1_TIMEOUT_SECONDS}s)") from e

        parsed = gemini_service._parse_json_response(response.text)
        return parsed, response.usage_metadata

    async def analyze(
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
        available_techstacks: list = None,
        change_metadata: str = "",
        infra_changes: str = "",
    ) -> tuple[dict, dict]:
        """
        Stage 1 분석 실행
        Returns: (분석 결과 딕셔너리, 토큰 사용량 정보)
        """
        prompt = get_feature_analysis_prompt(
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
            change_metadata=change_metadata,
            infra_changes=infra_changes,
            available_techstacks=available_techstacks,
        )

        logger.info(f"[FeatureAgent] Stage 1 분석 시작 (모델: {self.model_name})")
        parsed, usage = await self._generate_content(prompt)
        
        usage_info = {
            "prompt_tokens": getattr(usage, "prompt_token_count", 0),
            "candidates_tokens": getattr(usage, "candidates_token_count", 0),
            "total_tokens": getattr(usage, "total_token_count", 0),
        }
        logger.info(
            f"[FeatureAgent] Stage 1 완료 - 입력: {usage_info['prompt_tokens']}, "
            f"출력: {usage_info['candidates_tokens']}, 합계: {usage_info['total_tokens']}"
        )

        return parsed, usage_info
