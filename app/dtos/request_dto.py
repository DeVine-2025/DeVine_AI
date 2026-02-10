from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class ReportGenerationReq(BaseModel):
    detailReportId: int
    mainReportId: int
    gitUrl: str
    callbackUrl: str
    embeddingCallbackUrl: str
    githubToken: str
    techstacks: Optional[List[str]] = None


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
    techstacks: Optional[List[str]] = None
