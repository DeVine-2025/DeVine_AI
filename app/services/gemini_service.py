import re
import json
import asyncio
import logging
import google.generativeai as genai
from json_repair import repair_json
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from app.configs.settings import settings
from app.errors.exceptions import GeminiException
from app.utils.webhook import discord_send_message

logger = logging.getLogger(__name__)

genai.configure(api_key=settings.gemini_api_key)


FALLBACK_MODELS = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"]


class GeminiService:
    def __init__(self):
        self.model = genai.GenerativeModel(FALLBACK_MODELS[0])

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
        json_match = re.search(r"\{[\s\S]*\}", text)
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
        reraise=True,
    )
    def _generate_content_sync(self, prompt: str, model_name: str) -> dict:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json"
            ),
        )

        text = response.text
        return self._parse_json_response(text)

    async def generate_content(self, prompt: str) -> dict:
        last_error = None
        for model_name in FALLBACK_MODELS:
            try:
                return await asyncio.to_thread(
                    self._generate_content_sync, prompt, model_name
                )
            except Exception as e:
                error_str = str(e).lower()
                is_token_error = any(
                    k in error_str for k in ("token", "context", "too long", "400")
                )
                if is_token_error and model_name != FALLBACK_MODELS[-1]:
                    discord_send_message(
                        f"{model_name} 토큰 에러 발생, {FALLBACK_MODELS[FALLBACK_MODELS.index(model_name) + 1]}로 전환 시도: {str(e)}"
                    )
                    logger.warning(
                        f"{model_name} 토큰 에러, {FALLBACK_MODELS[FALLBACK_MODELS.index(model_name) + 1]}로 전환: {e}"
                    )
                    last_error = e
                    continue
                discord_send_message(f"{model_name} API 호출 실패: {str(e)}")
                raise GeminiException(f"Gemini API 호출 실패: {str(e)}")
        discord_send_message(f"모든 모델 실패: {str(last_error)}")
        raise GeminiException(f"모든 모델 실패: {str(last_error)}")

    async def analyze_code(self, prompt: str) -> dict:
        return await self.generate_content(prompt)


gemini_service = GeminiService()
