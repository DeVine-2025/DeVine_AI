"""백엔드 응답 계약 모델.

`gemini_service._REPORT_SCHEMA`의 main/detail과 1:1로 대응한다(techstacks는 별도 필드로 전달).
엔진은 이 모델을 돌려주고, 백엔드로 나가는 dict는 `to_legacy_dict()`로만 만든다.
"""
from pydantic import BaseModel


class Overview(BaseModel):
    summary: str
    mainTech: str
    capabilities: list[str]
    scale: str


class ProjectInfo(BaseModel):
    projectName: str
    techStack: list[str]
    scale: str


class KeyImplementation(BaseModel):
    title: str
    description: str
    capabilities: list[str]


class AiEvaluation(BaseModel):
    title: str
    details: list[str]


class MainReport(BaseModel):
    overview: Overview
    projectInfo: ProjectInfo
    keyImplementations: list[KeyImplementation]
    aiEvaluation: list[AiEvaluation]
    recommendations: list[str]


class TechStackEntry(BaseModel):
    title: str
    content: str


class ProjectScale(BaseModel):
    mainCodeFiles: int
    totalCodeLines: int
    developmentPeriod: str
    architecturePattern: str


class ProjectOverview(BaseModel):
    purpose: str
    techStack: list[TechStackEntry]
    projectScale: ProjectScale


class Feature(BaseModel):
    name: str
    implementation: list[str]
    codeLocation: list[str]
    details: list[str]


class FeatureCategory(BaseModel):
    category: str
    categoryNumber: int
    features: list[Feature]


class ProjectSummary(BaseModel):
    implemented: list[str]
    notImplemented: list[str]


class CodeInsight(BaseModel):
    number: int
    title: str
    points: list[str]
    codeLocation: list[str]


class Improvement(BaseModel):
    number: int
    title: str
    currentState: list[str]
    suggestions: list[str]
    keywords: str


class NextStep(BaseModel):
    number: int
    title: str
    description: list[str]
    recommendKeyword: list[str]


class DetailReport(BaseModel):
    reportTitle: str
    reportSubtitle: str
    projectOverview: ProjectOverview
    implementedFeatures: list[FeatureCategory]
    projectSummary: ProjectSummary
    codeInsights: list[CodeInsight]
    improvements: list[Improvement]
    nextSteps: list[NextStep]


class ReportContent(BaseModel):
    main: MainReport
    detail: DetailReport

    def to_legacy_dict(self) -> dict:
        return self.model_dump(mode="json")
