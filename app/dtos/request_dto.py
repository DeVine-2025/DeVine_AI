from typing import Any, Dict
from pydantic import BaseModel


class ReportGenerationReq(BaseModel):
    detailReportId: int
    mainReportId: int
    gitUrl: str
    callbackUrl: str
    githubToken: str


class EmbeddingReq(BaseModel):
    report: Dict[str, Any]


class ProjectEmbeddingReq(BaseModel):
    text: str
