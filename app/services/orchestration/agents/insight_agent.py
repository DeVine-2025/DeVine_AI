import json
import logging
import re
from google import genai
from google.genai import types

from app.configs.settings import settings
from app.services.orchestration.schemas.insight_schema import INSIGHT_SCHEMA
from app.services.orchestration.prompts.insight_prompt import INSIGHT_SYNTHESIS_PROMPT

logger = logging.getLogger(__name__)


class InsightAgent:
    """Stage 2: 1단계 추출 결과 기반 메인 리포트 요약 및 상세 리포트 생성 에이전트"""

    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self.model_name = model_name

    async def execute(
        self,
        repo_url: str,
        author_name: str,
        total_commits: int,
        user_commits: int,
        contribution_ratio: float,
        total_files: int,
        total_lines: int,
        development_period: str,
        stage1_output: dict,
        available_techstacks: list = None,
    ) -> dict:
        client = genai.Client(api_key=settings.gemini_api_key)

        prompt = INSIGHT_SYNTHESIS_PROMPT.format(
            repo_url=repo_url,
            author_name=author_name,
            total_commits=total_commits,
            user_commits=user_commits,
            contribution_ratio=contribution_ratio,
            total_files=total_files,
            total_lines=total_lines,
            development_period=development_period,
            available_techstacks=json.dumps(available_techstacks or [], ensure_ascii=False),
            stage1_json=json.dumps(stage1_output, ensure_ascii=False, indent=2),
        )

        logger.info(f"[InsightAgent] Stage 2 호출 시작 (모델: {self.model_name})")

        response = await client.aio.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=INSIGHT_SCHEMA,
                temperature=0.3,
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

        logger.info(f"[InsightAgent] Stage 2 완료. 입력 토큰: {token_usage['prompt_token_count']}, 출력 토큰: {token_usage['candidates_token_count']}")
        return {
            "data": result,
            "token_usage": token_usage,
        }
