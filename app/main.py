import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from app.routes import report_route
from app.middlewares.error_handler import add_exception_handlers

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = FastAPI(title="DeVine AI Server", version="1.0.0", lifespan=lifespan)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 서버 시작 중...")
    yield
    logger.info("🛑 서버 종료 중...")

add_exception_handlers(app)

app.include_router(
    report_route.router,
    prefix="/api/v1/reports",
    tags=["Reports"]
)


@app.get("/health")
async def health_check():
    """Docker 헬스체크용 엔드포인트"""
    return {"status": "healthy", "service": "DeVine AI Server"}
