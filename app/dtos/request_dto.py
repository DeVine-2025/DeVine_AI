from pydantic import BaseModel


class ReportGenerationReq(BaseModel):
    detailReportId: int
    mainReportId: int
    gitUrl: str
    callbackUrl: str
    githubToken: str
