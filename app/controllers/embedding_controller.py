import logging

from openai import APIError, RateLimitError, APIConnectionError

from app.dtos.embedding_dto import EmbeddingRequest, ProjectEmbeddingRequest, EmbeddingResponse
from app.services.embedding_service import EmbeddingService
from app.utils.text_processor import extract_embedding_text
from app.errors.exceptions import EmptyTextException, TextTooLongException, OpenAIException

logger = logging.getLogger(__name__)

MAX_INPUT_LENGTH = 30000


class EmbeddingController:
    def __init__(self):
        self.embedding_service = EmbeddingService()

    async def embed_report(self, request: EmbeddingRequest) -> EmbeddingResponse:
        text = extract_embedding_text(request.report)
        return await self._create_embedding(text)

    async def embed_project(self, request: ProjectEmbeddingRequest) -> EmbeddingResponse:
        return await self._create_embedding(request.text)

    async def _create_embedding(self, text: str) -> EmbeddingResponse:
        if not text.strip():
            raise EmptyTextException()
        if len(text) > MAX_INPUT_LENGTH:
            raise TextTooLongException(f"입력 텍스트 길이: {len(text)}자 (최대 {MAX_INPUT_LENGTH}자)")

        try:
            vector = await self.embedding_service.create_embedding(text)
            return EmbeddingResponse(vector=vector, dimension=len(vector))
        except (APIError, RateLimitError, APIConnectionError) as e:
            logger.error(f"OpenAI API 오류: {e}")
            raise OpenAIException(str(e))


embedding_controller = EmbeddingController()
