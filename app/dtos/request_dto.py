from typing import Any, Dict
from pydantic import BaseModel


class ReportGenerationReq(BaseModel):
    detailReportId: int
    mainReportId: int
    gitUrl: str
    callbackUrl: str
    embeddingCallbackUrl: str
    githubToken: str


class EmbeddingReq(BaseModel):
    report: Dict[str, Any]


class ProjectEmbeddingReq(BaseModel):
    text: str


class ReportGenerationSyncReq(BaseModel):
    mainReportId: int
    detailReportId: int
    gitUrl: str
    githubToken: str
    embeddingCallbackUrl: str
