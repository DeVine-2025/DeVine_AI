from pydantic import BaseModel
from typing import Optional, Any, List


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
    techstacks: Optional[List[str]] = None


class EmbeddingRes(BaseModel):
    vector: List[float]
    dimension: int


class EmbeddingCallbackReq(BaseModel):
    detailReportId: int
    mainReportId: int
    status: str
    vector: Optional[List[float]] = None
    dimension: Optional[int] = None
    errorMessage: Optional[str] = None


class ReportGenerationSyncRes(BaseModel):
    mainReportId: int
    detailReportId: int
    status: str
    content: Optional[Any] = None
    errorMessage: Optional[str] = None
    techstacks: Optional[List[str]] = None
