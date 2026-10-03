from dataclasses import dataclass, field
from typing import Dict, List, Optional, Protocol

from app.report.context import ReportContext


@dataclass
class EngineResult:
    """엔진 출력. 백엔드 응답 형태는 만들지 않는다(postprocess가 확정).

    content: main/detail 구조의 dict(후처리 전)
    tech_refs: {"projectInfo": [{name, dep}], "overview": [{title, items: [{name, dep}]}]} — 버전을 코드가 채울 때
    fallback_locations: 기능명 → 근거 경로. 검증 후 codeLocation이 비면 이 경로로 채운다
    """

    content: dict
    techstacks: List[str]
    usage: List[dict] = field(default_factory=list)
    events: List[dict] = field(default_factory=list)
    tech_refs: Optional[dict] = None
    fallback_locations: Optional[Dict[str, List[str]]] = None


class ReportEngine(Protocol):
    name: str

    async def generate(self, ctx: ReportContext) -> EngineResult: ...
