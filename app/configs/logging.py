import logging
import os
import sys
from logging.handlers import TimedRotatingFileHandler

from app.configs.settings import settings


def setup_logging() -> None:
    """애플리케이션 로깅 설정"""
<<<<<<< Updated upstream
    log_dir = settings.log_dir
=======
    log_dir = os.getenv("LOG_DIR", "/app/logs")
>>>>>>> Stashed changes
    os.makedirs(log_dir, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(settings.log_level)

    # 기존 핸들러 제거 (중복 방지)
    root_logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 콘솔 핸들러
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # 파일 핸들러 (날짜별 로테이션)
    file_handler = TimedRotatingFileHandler(
        filename=os.path.join(log_dir, "app.log"),
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8"
    )
    file_handler.suffix = "%Y-%m-%d"
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # uvicorn 로거 레벨 조정
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
