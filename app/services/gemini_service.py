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
    def _generate_content_sync(self, prompt: str, model_name: str) -> tuple[dict, object]:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json"
            ),
        )

        text = response.text
        return self._parse_json_response(text), response.usage_metadata

    # 각 모델별 입력 토큰 한도
    FLASH_TOKEN_LIMIT = 1_000_000  # gemini-2.5-flash: 1M
    PRO_TOKEN_LIMIT = 2_000_000  # gemini-2.5-pro:   2M
    # gemini-2.0-flash: 4M (초과 시 모두 실패로 처리)

    def _count_tokens_sync(self, prompt: str) -> int:
        """프롬프트 토큰 수 측정"""
        model = genai.GenerativeModel(FALLBACK_MODELS[0])
        return model.count_tokens(prompt).total_tokens

    def _select_start_model(self, token_count: int) -> int:
        """토큰 수에 따라 시작할 FALLBACK_MODELS 인덱스 반환"""
        if token_count > self.PRO_TOKEN_LIMIT:
            logger.info(
                f"토큰 수 {token_count:,} > {self.PRO_TOKEN_LIMIT:,}, gemini-2.0-flash로 시작"
            )
            discord_send_message(
                f"프롬프트 토큰 수 {token_count:,}개 - pro 한도 초과, {FALLBACK_MODELS[2]}로 시작"
            )
            return 2  # gemini-2.0-flash
        if token_count > self.FLASH_TOKEN_LIMIT:
            logger.info(
                f"토큰 수 {token_count:,} > {self.FLASH_TOKEN_LIMIT:,}, gemini-2.5-pro로 시작"
            )
            discord_send_message(
                f"프롬프트 토큰 수 {token_count:,}개 - flash 한도 초과, {FALLBACK_MODELS[1]}로 시작"
            )
            return 1  # gemini-2.5-pro
        return 0  # gemini-2.5-flash

    @staticmethod
    def _is_token_error(error_str: str) -> bool:
        """토큰/컨텍스트 관련 에러인지 판별 (400 오탐 방지)"""
        token_keywords = (
            "too long",
            "token limit",
            "context length",
            "context_length",
            "input_token",
            "payload size",
            "resource_exhausted",
            "context_window",
            "input too long",
            "maximum context",
        )
        if any(k in error_str for k in token_keywords):
            return True
        # 400이 size/length 관련일 때만 토큰 에러로 간주
        if "400" in error_str and any(
            k in error_str for k in ("size", "length", "limit")
        ):
            return True
        return False

    async def generate_content(self, prompt: str) -> dict:
        # 토큰 수 측정 후 시작 모델 결정
        try:
            token_count = await asyncio.to_thread(self._count_tokens_sync, prompt)
            logger.info(f"프롬프트 토큰 수: {token_count:,}")
        except Exception as e:
            logger.warning(f"토큰 카운트 실패, flash로 시작: {e}")
            token_count = 0

        start_idx = self._select_start_model(token_count)

        for model_name in FALLBACK_MODELS[start_idx:]:
            try:
                result, usage = await asyncio.to_thread(
                    self._generate_content_sync, prompt, model_name
                )
                if usage:
                    input_tokens = usage.prompt_token_count
                    output_tokens = usage.candidates_token_count
                    total_tokens = usage.total_token_count
                    logger.info(
                        f"[{model_name}] 토큰 사용량 - 입력: {input_tokens:,}, 출력: {output_tokens:,}, 합계: {total_tokens:,}"
                    )
                    discord_send_message(
                        f"[{model_name}] 토큰 사용량 — 입력: {input_tokens:,} / 출력: {output_tokens:,} / 합계: {total_tokens:,}"
                    )
                return result
            except Exception as e:
                error_str = str(e).lower()
                current_idx = FALLBACK_MODELS.index(model_name)
                is_last_model = current_idx == len(FALLBACK_MODELS) - 1

                if self._is_token_error(error_str):
                    if not is_last_model:
                        next_model = FALLBACK_MODELS[current_idx + 1]
                        discord_send_message(
                            f"{model_name} 토큰 에러 발생, {next_model}로 전환 시도: {str(e)}"
                        )
                        logger.warning(f"{model_name} 토큰 에러, {next_model}로 전환: {e}")
                        continue
                    discord_send_message(f"모든 모델 토큰 한도 초과, 분석 불가: {str(e)}")
                    raise GeminiException(f"모든 모델 토큰 한도 초과: {str(e)}")
                discord_send_message(f"{model_name} API 호출 실패: {str(e)}")
                raise GeminiException(f"Gemini API 호출 실패: {str(e)}")

    async def analyze_code(self, prompt: str) -> dict:
        return await self.generate_content(prompt)


gemini_service = GeminiService()
