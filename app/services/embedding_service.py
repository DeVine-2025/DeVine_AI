import logging

from openai import AsyncOpenAI, APIError, RateLimitError, APIConnectionError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.configs.settings import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.embedding_model
        self.dimension = settings.embedding_dimension

    @retry(
        retry=retry_if_exception_type((RateLimitError, APIConnectionError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        before_sleep=lambda retry_state: logger.warning(
            f"Retry attempt {retry_state.attempt_number} after error"
        ),
    )
    async def create_embedding(self, text: str) -> list[float]:
        """
        텍스트를 임베딩 벡터로 변환합니다.

        Args:
            text: 임베딩할 텍스트

        Returns:
            1536 차원의 임베딩 벡터

        Raises:
            APIError: OpenAI API 오류 (재시도 후에도 실패 시)
        """
        try:
            response = await self.client.embeddings.create(
                model=self.model,
                input=text,
                dimensions=self.dimension,
            )
            return response.data[0].embedding
        except (RateLimitError, APIConnectionError):
            raise
        except APIError as e:
            logger.error(f"OpenAI API error: {e}")
            raise


embedding_service = EmbeddingService()
