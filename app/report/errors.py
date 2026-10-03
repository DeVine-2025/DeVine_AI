from typing import Any, Optional


class ReportGenerationError(Exception):
    """리포트를 SUCCESS로 내보낼 수 없는 실패. analyzer가 FAILED 콜백/응답으로 바꾼다.

    reason: 분류용 짧은 코드(no_author_commits, contract_invalid, no_evidence, engine_failed ...)
    partial: 실패 직전까지 만든 결과(디버깅·평가용). 백엔드로 보내지 않는다.
    """

    def __init__(self, reason: str, message: str = "", partial: Any = None):
        self.reason = reason
        self.partial = partial
        self.outcome: Optional[Any] = None  # pipeline이 사용량·이벤트를 붙인다(평가용)
        super().__init__(f"{reason}: {message}" if message else reason)
