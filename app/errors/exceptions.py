class AppException(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


class GitCloneException(AppException):
    def __init__(self, message: str = "Git 클론 실패"):
        super().__init__(500, "GIT_CLONE_FAILED", message)


class GitAuthException(AppException):
    def __init__(self, message: str = "GitHub 인증 실패"):
        super().__init__(401, "GIT_AUTH_FAILED", message)


class RepoNotFoundException(AppException):
    def __init__(self, message: str = "레포지토리를 찾을 수 없습니다"):
        super().__init__(404, "REPO_NOT_FOUND", message)


class AnalysisException(AppException):
    def __init__(self, message: str = "코드 분석 실패"):
        super().__init__(500, "ANALYSIS_FAILED", message)


class GeminiException(AppException):
    def __init__(self, message: str = "Gemini API 호출 실패"):
        super().__init__(500, "GEMINI_API_FAILED", message)


class CallbackException(AppException):
    def __init__(self, message: str = "콜백 전송 실패"):
        super().__init__(500, "CALLBACK_FAILED", message)
