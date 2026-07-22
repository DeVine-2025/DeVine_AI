import re
import json
import logging
from google import genai
from google.genai import types, errors
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

client = genai.Client(api_key=settings.gemini_api_key)


_REPORT_SCHEMA = {
    "type": "object",
    "properties": {
        "techstacks": {"type": "array", "items": {"type": "string"}},
        "main": {
            "type": "object",
            "properties": {
                "overview": {
                    "type": "object",
                    "properties": {
                        "summary": {"type": "string"},
                        "mainTech": {"type": "string"},
                        "capabilities": {"type": "array", "items": {"type": "string"}},
                        "scale": {"type": "string"},
                    },
                    "required": ["summary", "mainTech", "capabilities", "scale"],
                },
                "projectInfo": {
                    "type": "object",
                    "properties": {
                        "projectName": {"type": "string"},
                        "techStack": {"type": "array", "items": {"type": "string"}},
                        "scale": {"type": "string"},
                    },
                    "required": ["projectName", "techStack", "scale"],
                },
                "keyImplementations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "description": {"type": "string"},
                            "capabilities": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["title", "description", "capabilities"],
                    },
                },
                "aiEvaluation": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "details": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["title", "details"],
                    },
                },
                "recommendations": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["overview", "projectInfo", "keyImplementations", "aiEvaluation", "recommendations"],
        },
        "detail": {
            "type": "object",
            "properties": {
                "reportTitle": {"type": "string"},
                "reportSubtitle": {"type": "string"},
                "projectOverview": {
                    "type": "object",
                    "properties": {
                        "purpose": {"type": "string"},
                        "techStack": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "title": {"type": "string"},
                                    "content": {"type": "string"},
                                },
                                "required": ["title", "content"],
                            },
                        },
                        "projectScale": {
                            "type": "object",
                            "properties": {
                                "mainCodeFiles": {"type": "number"},
                                "totalCodeLines": {"type": "number"},
                                "developmentPeriod": {"type": "string"},
                                "architecturePattern": {"type": "string"},
                            },
                            "required": ["mainCodeFiles", "totalCodeLines", "developmentPeriod", "architecturePattern"],
                        },
                    },
                    "required": ["purpose", "techStack", "projectScale"],
                },
                "implementedFeatures": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "category": {"type": "string"},
                            "categoryNumber": {"type": "number"},
                            "features": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "implementation": {"type": "array", "items": {"type": "string"}},
                                        "codeLocation": {"type": "array", "items": {"type": "string"}},
                                        "details": {"type": "array", "items": {"type": "string"}},
                                    },
                                    "required": ["name", "implementation", "codeLocation", "details"],
                                },
                            },
                        },
                        "required": ["category", "categoryNumber", "features"],
                    },
                },
                "projectSummary": {
                    "type": "object",
                    "properties": {
                        "implemented": {"type": "array", "items": {"type": "string"}},
                        "notImplemented": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["implemented", "notImplemented"],
                },
                "codeInsights": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "number": {"type": "number"},
                            "title": {"type": "string"},
                            "points": {"type": "array", "items": {"type": "string"}},
                            "codeLocation": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["number", "title", "points", "codeLocation"],
                    },
                },
                "improvements": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "number": {"type": "number"},
                            "title": {"type": "string"},
                            "currentState": {"type": "array", "items": {"type": "string"}},
                            "suggestions": {"type": "array", "items": {"type": "string"}},
                            "keywords": {"type": "string"},
                        },
                        "required": ["number", "title", "currentState", "suggestions", "keywords"],
                    },
                },
                "nextSteps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "number": {"type": "number"},
                            "title": {"type": "string"},
                            "description": {"type": "array", "items": {"type": "string"}},
                            "recommendKeyword": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["number", "title", "description", "recommendKeyword"],
                    },
                },
            },
            "required": ["reportTitle", "reportSubtitle", "projectOverview", "implementedFeatures", "projectSummary", "codeInsights", "improvements", "nextSteps"],
        },
    },
    "required": ["techstacks", "main", "detail"],
}


class GeminiService:
    FALLBACK_MODELS = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"]
    SYSTEM_INSTRUCTION = (
        "You are an expert at analyzing software project contributions and writing comprehensive reports. "
        "Write all values in the JSON response in Korean (한국어)."
    )
    REPORT_SCHEMA = _REPORT_SCHEMA

    # 각 모델별 입력 토큰 한도
    FLASH_TOKEN_LIMIT = 1_000_000  # gemini-2.5-flash: 1M
    PRO_TOKEN_LIMIT = 2_000_000  # gemini-2.5-pro:   2M
    # gemini-2.0-flash: 4M (초과 시 모두 실패로 처리)

    @staticmethod
    def _parse_json_response(text: str) -> dict:
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
        retry=retry_if_exception_type(errors.ServerError),
        reraise=True,
    )
    async def _generate_content(
        self, prompt: str, model_name: str
    ) -> tuple[dict, object]:
        response = await client.aio.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=self.SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                response_schema=self.REPORT_SCHEMA,
            ),
        )

        text = response.text
        if not text:
            raise GeminiException("Gemini 응답이 비어있습니다 (Safety filter 또는 빈 응답)")
        return self._parse_json_response(text), response.usage_metadata

    async def _count_tokens(self, prompt: str) -> int:
        """프롬프트 토큰 수 측정"""
        response = await client.aio.models.count_tokens(
            model=self.FALLBACK_MODELS[0],
            contents=prompt,
        )
        return response.total_tokens

    def _select_start_model(self, token_count: int) -> int:
        """토큰 수에 따라 시작할 FALLBACK_MODELS 인덱스 반환"""
        if token_count > self.PRO_TOKEN_LIMIT:
            logger.info(
                f"토큰 수 {token_count:,} > {self.PRO_TOKEN_LIMIT:,}, gemini-2.0-flash로 시작"
            )
            return 2  # gemini-2.0-flash
        if token_count > self.FLASH_TOKEN_LIMIT:
            logger.info(
                f"토큰 수 {token_count:,} > {self.FLASH_TOKEN_LIMIT:,}, gemini-2.5-pro로 시작"
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
            "context_window",
            "input too long",
            "maximum context",
        )
        if any(k in error_str for k in token_keywords):
            return True
        # 400이 size/length 관련일 때만 토큰 에러로 간주
        if "400" in error_str and "invalid_argument" not in error_str and any(
            k in error_str for k in ("size", "length", "limit")
        ):
            return True
        return False

    async def generate_content(self, prompt: str) -> dict:
        # 토큰 수 측정 후 시작 모델 결정
        try:
            token_count = await self._count_tokens(prompt)
            logger.info(f"프롬프트 토큰 수: {token_count:,}")
        except Exception as e:
            logger.warning(f"토큰 카운트 실패, flash로 시작: {e}")
            token_count = 0

        start_idx = self._select_start_model(token_count)
        if start_idx > 0:
            discord_send_message(
                f"프롬프트 토큰 수 {token_count:,}개 - {self.FALLBACK_MODELS[start_idx]}로 시작"
            )

        for current_idx, model_name in enumerate(self.FALLBACK_MODELS[start_idx:], start=start_idx):
            try:
                result, usage = await self._generate_content(prompt, model_name)
                if usage:
                    input_tokens = usage.prompt_token_count
                    output_tokens = usage.candidates_token_count
                    total_tokens = usage.total_token_count
                    logger.info(
                        f"[{model_name}] 토큰 사용량 - 입력: {input_tokens:,}, 출력: {output_tokens:,}, 합계: {total_tokens:,}"
                    )
                return result
            except Exception as e:
                error_str = str(e).lower()
                is_last_model = current_idx == len(self.FALLBACK_MODELS) - 1

                if self._is_token_error(error_str):
                    if not is_last_model:
                        next_model = self.FALLBACK_MODELS[current_idx + 1]
                        logger.warning(
                            f"{model_name} 토큰 에러, {next_model}로 전환: {e}"
                        )
                        discord_send_message(
                            f"{model_name} 토큰 에러 발생, {next_model}로 전환 시도: {str(e)}"
                        )
                        continue
                    logger.error(f"모든 모델 토큰 한도 초과, 분석 불가: {e}")
                    discord_send_message(
                        f"모든 모델 토큰 한도 초과, 분석 불가: {str(e)}"
                    )
                    raise GeminiException(f"모든 모델 토큰 한도 초과: {str(e)}") from e
                logger.error(f"{model_name} API 호출 실패: {e}")
                discord_send_message(f"{model_name} API 호출 실패: {str(e)}")
                raise GeminiException(f"Gemini API 호출 실패: {str(e)}") from e

    async def analyze_code(self, prompt: str) -> dict:
        return await self.generate_content(prompt)


gemini_service = GeminiService()
