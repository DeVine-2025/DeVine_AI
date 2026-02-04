from pydantic import BaseModel
from typing import Optional, Any


class ReportGenerationRes(BaseModel):
    detailReportId: int
    mainReportId: int
    status: str
    message: str


class CallbackReq(BaseModel):
    detailReportId: int
    mainReportId: int
    status: str
    content: Optional[Any] = None
    errorMessage: Optional[str] = None
