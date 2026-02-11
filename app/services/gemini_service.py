import re
import json
import asyncio
import logging
import google.generativeai as genai
from json_repair import repair_json
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from app.configs.settings import settings
from app.errors.exceptions import GeminiException

logger = logging.getLogger(__name__)

genai.configure(api_key=settings.gemini_api_key)


class GeminiService:
    def __init__(self):
        self.model = genai.GenerativeModel("gemini-2.5-flash")

    def _parse_json_response(self, text: str) -> dict:
        """JSON 응답 파싱 - 실패 시 복구 시도"""
        # 1차: 직접 파싱 시도
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 2차: json_repair로 복구 시도
        try:
            repaired = repair_json(text, return_objects=True)
            if isinstance(repaired, dict):
                logger.info("JSON 복구 성공 (json_repair)")
                return repaired
        except Exception:
            pass

        # 3차: 정규식으로 JSON 추출 후 복구 시도
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            try:
                repaired = repair_json(json_match.group(), return_objects=True)
                if isinstance(repaired, dict):
                    logger.info("JSON 복구 성공 (정규식 + json_repair)")
                    return repaired
            except Exception:
                pass

        raise GeminiException("Gemini 응답을 JSON으로 파싱할 수 없습니다")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(GeminiException),
        reraise=True
    )
    def _generate_content_sync(self, prompt: str) -> dict:
        response = self.model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json"
            )
        )

        text = response.text
        return self._parse_json_response(text)

    async def generate_content(self, prompt: str) -> dict:
        try:
            return await asyncio.to_thread(self._generate_content_sync, prompt)
        except GeminiException:
            raise
        except Exception as e:
            raise GeminiException(f"Gemini API 호출 실패: {str(e)}")

    async def analyze_code(self, prompt: str) -> dict:
        return await self.generate_content(prompt)


gemini_service = GeminiService()
