from enum import Enum


class ErrorCode(str, Enum):
    """에러 코드 정의"""

    # 400 Bad Request
    EMPTY_TEXT = "EMPTY_TEXT"
    INVALID_REPORT_FORMAT = "INVALID_REPORT_FORMAT"
    TEXT_TOO_LONG = "TEXT_TOO_LONG"

    # 500 Internal Server Error
    EMBEDDING_FAILED = "EMBEDDING_FAILED"
    OPENAI_API_ERROR = "OPENAI_API_ERROR"

    @property
    def message(self) -> str:
        return ERROR_MESSAGES.get(self, "알 수 없는 오류가 발생했습니다.")


ERROR_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.EMPTY_TEXT: "리포트에서 임베딩할 텍스트를 추출할 수 없습니다.",
    ErrorCode.INVALID_REPORT_FORMAT: "리포트 형식이 올바르지 않습니다.",
    ErrorCode.TEXT_TOO_LONG: "입력 텍스트가 너무 깁니다. 최대 30,000자까지 허용됩니다.",
    ErrorCode.EMBEDDING_FAILED: "임베딩 생성 중 오류가 발생했습니다.",
    ErrorCode.OPENAI_API_ERROR: "OpenAI API 호출 중 오류가 발생했습니다.",
}


class AppException(Exception):
    """애플리케이션 기본 예외"""

    def __init__(
        self,
        error_code: ErrorCode,
        status_code: int = 500,
        detail: str | None = None,
    ):
        self.error_code = error_code
        self.status_code = status_code
        self.detail = detail or error_code.message
        super().__init__(self.detail)


class BadRequestException(AppException):
    """400 Bad Request"""

    def __init__(self, error_code: ErrorCode, detail: str | None = None):
        super().__init__(error_code, status_code=400, detail=detail)


class InternalServerException(AppException):
    """500 Internal Server Error"""

    def __init__(self, error_code: ErrorCode, detail: str | None = None):
        super().__init__(error_code, status_code=500, detail=detail)
