"""섹션 출력 스키마 (요청마다 enum이 달라 동적으로 만든다).

원칙(스파이크 0-2): 배열은 max_length만 둔다. min_length를 주면 모델이 데이터가 모자랄 때 항목을 지어낸다.
fid·file_id·dep 같은 ID 필드는 LLM 출력에만 있고 계약 모델로 옮길 때 코드가 경로·버전으로 바꾼다.
"""
from typing import List, Literal, Type

from pydantic import BaseModel, Field, create_model

ROOT_TECHSTACKS = {"BACKEND", "FRONTEND", "INFRA"}
NO_DEP = "none"


def _lit(values) -> type:
    values = tuple(dict.fromkeys(values))
    return Literal[values] if values else str  # type: ignore[valid-type]


def _list(t, n: int, desc: str = ""):
    return (List[t], Field(max_length=n, description=desc))


def tech_model(available_techstacks: List[str]) -> Type[BaseModel]:
    techs = [t for t in available_techstacks if t not in ROOT_TECHSTACKS]
    # dep을 enum으로 묶으면 중첩 배열과 곱해져 Gemini가 "too many states"(400)로 거부한다(1-x 실측).
    # 자유 문자열로 받고 후처리가 버전 표에 있는 키만 버전으로 바꾼다(없으면 이름만, version_missing).
    TechItem = create_model(
        "TechItem",
        name=(str, Field(description="기술 이름(버전 숫자 없이)")),
        dep=(str, Field(description=f"의존성 표의 키를 그대로. 표에 없으면 {NO_DEP}")),
    )
    Group = create_model("TechGroup", title=(str, ...), items=_list(TechItem, 8))
    return create_model(
        "TechSection",
        techstacks=_list(_lit(techs), 10, "작성자가 직접 사용한 기술 enum"),
        projectTech=_list(TechItem, 10, "프로젝트 전체 주요 기술"),
        overviewGroups=_list(Group, 7, "카테고리별 기술 묶음"),
    )


def features_model(fids: List[str], other_ids: List[str]) -> Type[BaseModel]:
    Item = create_model(
        "FeatureItem",
        fid=(_lit(fids), Field(description="검증된 기능 ID")),
        name=(str, ...),
        implementation=_list(str, 3),
        details=_list(str, 3),
    )
    Category = create_model("FeatureCategory", category=(str, ...), features=_list(Item, 4))
    fields = dict(
        purpose=(str, Field(description="프로젝트 목적 2~3문장")),
        categories=_list(Category, 5),
        implemented=_list(str, 5),
    )
    if other_ids:
        NotImpl = create_model("NotImplemented", text=(str, ...), file_id=(_lit(other_ids), Field(description="다른 기여자 소유 파일 ID")))
        fields["notImplemented"] = _list(NotImpl, 3)
    return create_model("FeaturesSection", **fields)


def insights_model(file_ids: List[str]) -> Type[BaseModel]:
    Insight = create_model("Insight", title=(str, ...), points=_list(str, 3), file_ids=_list(_lit(file_ids), 3))
    Improvement = create_model(
        "Improvement", title=(str, ...), currentState=_list(str, 2), suggestions=_list(str, 3), keywords=(str, ...)
    )
    NextStep = create_model("NextStep", title=(str, ...), description=_list(str, 3), recommendKeyword=_list(str, 3))
    return create_model(
        "InsightsSection",
        architecturePattern=(str, ...),
        codeInsights=_list(Insight, 4),
        improvements=_list(Improvement, 3),
        nextSteps=_list(NextStep, 3),
    )


def main_model(fids: List[str]) -> Type[BaseModel]:
    KeyImpl = create_model(
        "KeyImplementation", fid=(_lit(fids), ...), title=(str, ...), description=(str, ...), capabilities=_list(str, 4)
    )
    Eval = create_model("AiEvaluation", title=(str, ...), details=_list(str, 3))
    return create_model(
        "MainSection",
        summary=(str, ...),
        mainTech=(str, ...),
        capabilities=_list(str, 5),
        keyImplementations=_list(KeyImpl, 4),
        aiEvaluation=_list(Eval, 3),
        recommendations=_list(str, 3),
    )


def card_model(file_ids: List[str], commit_ids: List[str]) -> Type[BaseModel]:
    """V1 Map 근거 카드. 파일·커밋 ID는 해당 청크에 있는 것만 고를 수 있다."""
    Feature = create_model(
        "CardFeature",
        name=(str, ...),
        summary=(str, Field(description="코드가 실제로 하는 일 1~2문장")),
        level_hint=(Literal["created", "major", "minor"], ...),
        file_ids=_list(_lit(file_ids), 5),
        commit_ids=_list(_lit(commit_ids), 5),
    )
    return create_model(
        "EvidenceCard",
        features=_list(Feature, 8),
        patterns=_list(str, 4),
        risks=_list(str, 4),
        notes=_list(str, 3),
    )

