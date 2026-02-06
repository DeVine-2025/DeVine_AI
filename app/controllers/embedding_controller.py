import logging

from openai import APIError, RateLimitError, APIConnectionError

from app.dtos.request_dto import EmbeddingReq, ProjectEmbeddingReq
from app.dtos.response_dto import EmbeddingRes
from app.services.embedding_service import embedding_service
from app.utils.text_processor import extract_embedding_text
from app.errors.exceptions import EmptyTextException, TextTooLongException, OpenAIException

logger = logging.getLogger(__name__)

MAX_INPUT_LENGTH = 30000


class EmbeddingController:
    async def embed_report(self, request: EmbeddingReq) -> EmbeddingRes:
        text = extract_embedding_text(request.report)
        return await self._create_embedding(text)

    async def embed_project(self, request: ProjectEmbeddingReq) -> EmbeddingRes:
        return await self._create_embedding(request.text)

    async def _create_embedding(self, text: str) -> EmbeddingRes:
        if not text.strip():
            raise EmptyTextException()
        if len(text) > MAX_INPUT_LENGTH:
            raise TextTooLongException(f"입력 텍스트 길이: {len(text)}자 (최대 {MAX_INPUT_LENGTH}자)")

        try:
            vector = await embedding_service.create_embedding(text)
            return EmbeddingRes(vector=vector, dimension=len(vector))
        except (APIError, RateLimitError, APIConnectionError) as e:
            logger.error(f"OpenAI API 오류: {e}")
            raise OpenAIException(str(e))


embedding_controller = EmbeddingController()
