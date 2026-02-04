from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ErrorResponse(BaseModel):
    """에러 응답 모델"""

    success: bool = False
    error_code: str
    message: str
    detail: str | None = None


class SuccessResponse(BaseModel, Generic[T]):
    """성공 응답 모델 (필요시 사용)"""

    success: bool = True
    data: T
