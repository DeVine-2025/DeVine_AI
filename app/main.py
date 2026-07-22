import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from app.routes import report_route, embedding_route
from app.middlewares.error_handler import add_exception_handlers
from app.configs.logging import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 서버 시작 중...")
    yield
    logger.info("🛑 서버 종료 중...")

app = FastAPI(title="DeVine AI Server", version="1.0.10", lifespan=lifespan)

add_exception_handlers(app)

app.include_router(
    report_route.router,
    prefix="/api/v1/reports",
    tags=["Reports"]
)

app.include_router(
    embedding_route.router,
    prefix="/api/v1/embeddings",
    tags=["Embedding"]
)


@app.get("/health")
async def health_check():
    """Docker 헬스체크용 엔드포인트"""
    return {"status": "healthy", "service": "DeVine AI Server"}
