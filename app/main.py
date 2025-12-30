import logging

from fastapi import FastAPI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = FastAPI(title="DeVine AI Server", version="1.0.0")

@app.on_event("startup")
async def on_startup():
    logger.info("🚀 서버 시작 중...")

@app.on_event("shutdown")
async def on_shutdown():
    logger.info("🛑 서버 종료 중...")

@app.get("/health")
async def health_check():
    """Docker 헬스체크용 엔드포인트"""
    return {"status": "healthy", "service": "DeVine AI Server"}
