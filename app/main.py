import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.config import get_settings
from openai import APIError, APIConnectionError, RateLimitError

from app.core.exceptions import (
    AppException,
    BadRequestException,
    ErrorCode,
    InternalServerException,
)
from app.core.response import ErrorResponse
from app.services.embedding_service import EmbeddingService
from app.utils.text_processor import extract_embedding_text

# 최대 입력 텍스트 길이 (약 8191 토큰에 대응하는 문자 수)
MAX_INPUT_LENGTH = 30000

# 로그 설정
settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# === Lifespan ===


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 생명주기 관리"""
    # Startup
    logger.info("서버 시작 중...")
    app.state.embedding_service = EmbeddingService()
    logger.info(f"임베딩 모델: {settings.EMBEDDING_MODEL}")
    logger.info(f"로그 레벨: {settings.LOG_LEVEL}")

    yield

    # Shutdown
    logger.info("서버 종료 중...")


app = FastAPI(title="DeVine AI Server", version="1.0.0", lifespan=lifespan)


# === Dependencies ===


def get_embedding_service(request: Request) -> EmbeddingService:
    """EmbeddingService 의존성 주입"""
    return request.app.state.embedding_service


# === Request/Response Models ===


class EmbeddingRequest(BaseModel):
    report: dict[str, Any]


class ProjectEmbeddingRequest(BaseModel):
    text: str


class EmbeddingResponse(BaseModel):
    vector: list[float]
    dimension: int


# === Exception Handlers ===


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    """커스텀 예외 핸들러"""
    logger.error(f"[{exc.error_code}] {exc.detail}")

    # DEBUG 모드가 아니면 상세 정보 숨김
    show_detail = settings.DEBUG and exc.detail != exc.error_code.message

    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error_code=exc.error_code.value,
            message=exc.error_code.message,
            detail=exc.detail if show_detail else None,
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """예상치 못한 예외 핸들러"""
    logger.exception(f"Unexpected error: {exc}")
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error_code="INTERNAL_ERROR",
            message="서버 내부 오류가 발생했습니다.",
            detail=str(exc) if settings.DEBUG else None,
        ).model_dump(),
    )


# === Helper Functions ===


def _validate_text_length(text: str) -> None:
    """텍스트 길이 검증"""
    if len(text) > MAX_INPUT_LENGTH:
        raise BadRequestException(
            ErrorCode.TEXT_TOO_LONG,
            detail=f"입력 텍스트 길이: {len(text)}자 (최대 {MAX_INPUT_LENGTH}자)",
        )


async def _create_embedding_with_error_handling(
    embedding_service: EmbeddingService,
    text: str,
) -> list[float]:
    """임베딩 생성 및 에러 처리"""
    try:
        return await embedding_service.create_embedding(text)
    except (RateLimitError, APIConnectionError, APIError) as e:
        logger.error(f"OpenAI API 오류: {e}")
        raise InternalServerException(
            ErrorCode.OPENAI_API_ERROR,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"임베딩 생성 실패: {e}")
        raise InternalServerException(
            ErrorCode.EMBEDDING_FAILED,
            detail=str(e),
        )


# === Endpoints ===


@app.get("/health")
async def health_check():
    """Docker 헬스체크용 엔드포인트"""
    return {"status": "healthy", "service": "DeVine AI Server"}


@app.post("/embed", response_model=EmbeddingResponse)
async def embed_report(
    request: EmbeddingRequest,
    embedding_service: EmbeddingService = Depends(get_embedding_service),
):
    """
    리포트 JSON을 받아 임베딩 벡터를 반환합니다.

    - 리포트에서 핵심 텍스트 추출 (summary, mainTech, techStack, 구현 제목)
    - OpenAI text-embedding-3-small 모델로 임베딩
    - 1536 차원 벡터 반환
    """
    logger.info("임베딩 요청 수신")
    logger.debug(f"리포트 키: {list(request.report.keys())}")

    text = extract_embedding_text(request.report)

    if not text.strip():
        raise BadRequestException(ErrorCode.EMPTY_TEXT)

    _validate_text_length(text)
    logger.debug(f"추출된 텍스트 길이: {len(text)}자")

    vector = await _create_embedding_with_error_handling(embedding_service, text)
    logger.info(f"임베딩 생성 완료 (dimension: {len(vector)})")

    return EmbeddingResponse(
        vector=vector,
        dimension=len(vector),
    )


@app.post("/embed/project", response_model=EmbeddingResponse)
async def embed_project(
    request: ProjectEmbeddingRequest,
    embedding_service: EmbeddingService = Depends(get_embedding_service),
):
    """
    프로젝트 공고 텍스트를 받아 임베딩 벡터를 반환합니다.

    - Spring 서버에서 도메인 정보가 포함된 텍스트를 조합하여 전송
    - OpenAI text-embedding-3-small 모델로 임베딩
    - 1536 차원 벡터 반환
    """
    logger.info("프로젝트 임베딩 요청 수신")

    if not request.text.strip():
        raise BadRequestException(ErrorCode.EMPTY_TEXT)

    _validate_text_length(request.text)
    logger.debug(f"텍스트 길이: {len(request.text)}자")

    vector = await _create_embedding_with_error_handling(embedding_service, request.text)
    logger.info(f"프로젝트 임베딩 생성 완료 (dimension: {len(vector)})")

    return EmbeddingResponse(
        vector=vector,
        dimension=len(vector),
    )
