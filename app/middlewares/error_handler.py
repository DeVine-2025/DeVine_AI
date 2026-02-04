from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.errors.exceptions import AppException


def add_exception_handlers(app: FastAPI):
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "isSuccess": False,
                "code": exc.code,
                "message": exc.message
            }
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={
                "isSuccess": False,
                "code": "INTERNAL_ERROR",
                "message": str(exc)
            }
        )
