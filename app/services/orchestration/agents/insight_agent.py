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
from app.services.orchestration.schemas.insight_schema import INSIGHT_SCHEMA
from app.services.orchestration.prompts.insight_prompt import get_insight_analysis_prompt
from app.services.gemini_service import gemini_service
from app.errors.exceptions import GeminiException

logger = logging.getLogger(__name__)

client = genai.Client(api_key=settings.gemini_api_key)


class InsightAgent:
    """
    Stage 2: 인사이트 생성 에이전트 (Evaluation & Synthesis)
    Stage 1에서 검증된 정제된 기능 목록과 코드 인사이트만을 바탕으로
    개발자 평가, 프로젝트 개요, 개선점 및 향후 단계를 도출합니다.
    """

    SYSTEM_INSTRUCTION = (
        "You are an executive engineering manager and principal tech evaluator. "
        "Provide insightful, professional evaluation grounded in verified implementation facts. "
        "Write all natural language descriptions in Korean (한국어)."
    )

    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self.model_name = model_name

    STAGE2_TIMEOUT_SECONDS = 45

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
                        response_schema=INSIGHT_SCHEMA,
                    ),
                ),
                timeout=self.STAGE2_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError as e:
            logger.error(f"[InsightAgent] Stage 2 타임아웃 발생 ({self.STAGE2_TIMEOUT_SECONDS}초 초과)")
            raise GeminiException(f"Stage 2 LLM 호출 시간 초과 ({self.STAGE2_TIMEOUT_SECONDS}s)") from e

        parsed = gemini_service._parse_json_response(response.text)
        return parsed, response.usage_metadata

    async def analyze(
        self,
        repo_url: str,
        author_name: str,
        total_files: int,
        total_lines: int,
        development_period: str,
        verified_feature_result: dict,
    ) -> tuple[dict, dict]:
        """
        Stage 2 분석 실행
        Returns: (분석 결과 딕셔너리, 토큰 사용량 정보)
        """
        # Stage 1에서 검증된 데이터를 읽기 쉬운 요약 문자열로 포맷팅
        author_techstacks = ", ".join(verified_feature_result.get("techstacks", []))

        key_impls = verified_feature_result.get("keyImplementations", [])
        key_impls_str = "\n".join([
            f"- {item.get('title')}: {item.get('description')} (역량: {', '.join(item.get('capabilities', []))})"
            for item in key_impls
        ])

        categories = verified_feature_result.get("implementedFeatures", [])
        cat_lines = []
        for cat in categories:
            cat_lines.append(f"[{cat.get('category')}]")
            for f in cat.get("features", []):
                locs = ", ".join(f.get("codeLocation", []))
                cat_lines.append(f"  * {f.get('name')}: {'; '.join(f.get('implementation', []))} (위치: {locs})")
        verified_features_str = "\n".join(cat_lines)

        proj_summary = verified_feature_result.get("projectSummary", {})
        impl_summary = "\n".join([f"- {x}" for x in proj_summary.get("implemented", [])])
        not_impl_summary = "\n".join([f"- {x}" for x in proj_summary.get("notImplemented", [])])

        # v3 메타데이터 및 인프라 요약 추출
        migration_meta = verified_feature_result.get("migrationMeta", {})
        migration_str = ""
        if migration_meta:
            migration_str = (
                f"- 총 수정 파일: {migration_meta.get('totalFilesModified', 0)}개\n"
                f"- 대규모 리팩토링 여부: {migration_meta.get('isLargeScale', False)}\n"
                f"- 범위 맥락: {migration_meta.get('scopeDescription', '')}"
            )

        infra_work = verified_feature_result.get("infraAndDevOps", {})
        infra_str = ""
        if infra_work and infra_work.get("hasInfraWork"):
            techs = ", ".join(infra_work.get("technologies", []))
            files = ", ".join(infra_work.get("keyFiles", []))
            infra_str = (
                f"- 인프라 기술: {techs}\n"
                f"- 핵심 기여: {infra_work.get('summary', '')}\n"
                f"- 관련 설정 파일: {files}"
            )

        prompt = get_insight_analysis_prompt(
            repo_url=repo_url,
            author_name=author_name,
            total_files=total_files,
            total_lines=total_lines,
            development_period=development_period,
            author_techstacks=author_techstacks,
            key_implementations_summary=key_impls_str,
            verified_features_summary=verified_features_str,
            implemented_summary=impl_summary,
            not_implemented_summary=not_impl_summary,
            migration_metadata_summary=migration_str,
            infra_contributions_summary=infra_str,
        )

        logger.info(f"[InsightAgent] Stage 2 분석 시작 (모델: {self.model_name})")
        parsed, usage = await self._generate_content(prompt)

        usage_info = {
            "prompt_tokens": getattr(usage, "prompt_token_count", 0),
            "candidates_tokens": getattr(usage, "candidates_token_count", 0),
            "total_tokens": getattr(usage, "total_token_count", 0),
        }
        logger.info(
            f"[InsightAgent] Stage 2 완료 - 입력: {usage_info['prompt_tokens']}, "
            f"출력: {usage_info['candidates_tokens']}, 합계: {usage_info['total_tokens']}"
        )

        return parsed, usage_info
