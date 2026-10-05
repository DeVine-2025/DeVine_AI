import json
import logging
import re
from google import genai
from google.genai import types

from app.configs.settings import settings
from app.services.orchestration.schemas.feature_schema import FEATURE_SCHEMA
from app.services.orchestration.prompts.feature_prompt import FEATURE_EXTRACTION_PROMPT

logger = logging.getLogger(__name__)


class FeatureAgent:
    """Stage 1: 전체 diff/tree에서 기여 기능 및 파일 경로 1차 추출 에이전트"""

    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self.model_name = model_name

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
    ) -> dict:
        client = genai.Client(api_key=settings.gemini_api_key)

        prompt = FEATURE_EXTRACTION_PROMPT.format(
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

        logger.info(f"[FeatureAgent] Stage 1 호출 시작 (모델: {self.model_name})")

        response = await client.aio.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=FEATURE_SCHEMA,
                temperature=0.2,
            ),
        )

        response_text = response.text
        json_match = re.search(r"```json\s*([\s\S]*?)\s*```", response_text)
        if json_match:
            response_text = json_match.group(1)

        result = json.loads(response_text)
        usage = response.usage_metadata
        token_usage = {
            "prompt_token_count": usage.prompt_token_count if usage else 0,
            "candidates_token_count": usage.candidates_token_count if usage else 0,
            "total_token_count": usage.total_token_count if usage else 0,
        }

        logger.info(f"[FeatureAgent] Stage 1 완료. 입력 토큰: {token_usage['prompt_token_count']}, 출력 토큰: {token_usage['candidates_token_count']}")
        return {
            "data": result,
            "token_usage": token_usage,
        }
