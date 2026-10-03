"""모든 엔진 공통 후처리 (계획 §4.4).

순서: 코드로 채우기 → 버전 채우기 → 번호 다시 매기기 → 경로 검증 → techstacks 필터 → 배열 개수 → 계약 검증.
보정할 때마다 corrections[종류]에 건수를 더한다. 모자란 배열은 채우지 않는다(지어내기 방지).
"""
import copy
import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from pydantic import ValidationError

from app.report.context import ReportContext
from app.report.contract import ReportContent
from app.report.errors import ReportGenerationError

logger = logging.getLogger(__name__)

REPORT_SUBTITLE = "프로젝트 상세 분석 리포트"
ROOT_TECHSTACKS = {"BACKEND", "FRONTEND", "INFRA"}

# 프롬프트가 요구하는 배열 개수 (min, max). 경로의 []는 "각 항목의 하위 배열".
ARRAY_LIMITS = {
    "main.overview.capabilities": (5, 5),
    "main.projectInfo.techStack": (5, 10),
    "main.keyImplementations": (4, 4),
    "main.keyImplementations[].capabilities": (4, 4),
    "main.aiEvaluation": (3, 3),
    "main.aiEvaluation[].details": (3, 3),
    "main.recommendations": (3, 3),
    "detail.implementedFeatures": (1, 5),
    "detail.implementedFeatures[].features": (2, 4),
    "detail.implementedFeatures[].features[].implementation": (2, 3),
    "detail.implementedFeatures[].features[].details": (2, 3),
    "detail.projectSummary.implemented": (3, 5),
    "detail.projectSummary.notImplemented": (0, 3),
    "detail.codeInsights": (4, 4),
    "detail.codeInsights[].points": (2, 3),
    "detail.improvements": (3, 3),
    "detail.improvements[].currentState": (1, 2),
    "detail.improvements[].suggestions": (2, 3),
    "detail.nextSteps": (3, 3),
    "detail.nextSteps[].description": (2, 3),
    "detail.nextSteps[].recommendKeyword": (2, 3),
}

_TRAILING_VERSION = re.compile(r"\s*v?\d+(?:\.\d+)*(?:\.x)?\s*$")


@dataclass
class PostprocessResult:
    content: ReportContent
    techstacks: List[str]
    corrections: Dict[str, int] = field(default_factory=dict)


def _section(d: dict, *keys) -> dict:
    for k in keys:
        if not isinstance(d.get(k), dict):
            d[k] = {}
        d = d[k]
    return d


def fill_from_code(c: dict, ctx: ReportContext) -> None:
    f = ctx.facts
    main, detail = _section(c, "main"), _section(c, "detail")
    _section(main, "overview")["scale"] = (
        f"{f.author_added:,}줄 추가 · {f.author_files_modified}개 파일 수정 · {f.author_period} 활동"
    )
    info = _section(main, "projectInfo")
    info["projectName"] = ctx.project_name
    info["scale"] = f"{f.project_code_lines}줄 | {f.project_code_files}개 파일 | {f.project_period} 개발 기간"
    detail["reportTitle"] = ctx.project_name
    detail["reportSubtitle"] = REPORT_SUBTITLE
    scale = _section(detail, "projectOverview", "projectScale")
    scale["mainCodeFiles"] = f.project_code_files
    scale["totalCodeLines"] = f.project_code_lines
    scale["developmentPeriod"] = f.project_period
    scale.setdefault("architecturePattern", "")


def _render_tech(item: dict, versions: Dict[str, str], corr: Counter) -> str:
    name = (item.get("name") or "").strip()
    dep = (item.get("dep") or "").strip()
    if not dep:
        return name
    base = _TRAILING_VERSION.sub("", name) or name
    version = versions.get(dep) or versions.get(dep.lower())
    if version:
        corr["version_filled"] += 1
        return f"{base} {version}"
    corr["version_missing"] += 1
    return base


def fill_versions(c: dict, tech_refs: Optional[dict], ctx: ReportContext, corr: Counter) -> None:
    if not tech_refs:
        return
    if tech_refs.get("projectInfo") is not None:
        _section(c, "main", "projectInfo")["techStack"] = [
            _render_tech(it, ctx.build_versions, corr) for it in tech_refs["projectInfo"]
        ]
    if tech_refs.get("overview") is not None:
        _section(c, "detail", "projectOverview")["techStack"] = [
            {"title": g.get("title", ""), "content": ", ".join(_render_tech(it, ctx.build_versions, corr) for it in g.get("items", []))}
            for g in tech_refs["overview"]
        ]


def renumber(c: dict) -> None:
    detail = c.get("detail") or {}
    for i, cat in enumerate(detail.get("implementedFeatures") or [], start=1):
        if isinstance(cat, dict):
            cat["categoryNumber"] = i
    for key in ("codeInsights", "improvements", "nextSteps"):
        for i, item in enumerate(detail.get(key) or [], start=1):
            if isinstance(item, dict):
                item["number"] = i


def normalize_path(p: str) -> str:
    p = p.strip().strip("`'\"").strip()
    p = re.sub(r"^\./", "", p).lstrip("/")
    p = re.split(r"(?::\d|#L\d|\s\(|\s-\s)", p)[0]
    return p.strip()


def _verify_paths(paths, ctx: ReportContext, corr: Counter) -> List[str]:
    head = ctx.head_file_set
    out: List[str] = []
    for raw in paths or []:
        if not isinstance(raw, str):
            corr["path_dropped"] += 1
            continue
        p = normalize_path(raw)
        if p not in head and p in ctx.rename_map:
            p = ctx.rename_map[p]
            corr["path_renamed"] += 1
        is_dir = p.endswith("/") and any(h.startswith(p) for h in head)
        if p in head or is_dir:
            if p not in out:
                out.append(p)
        else:
            corr["path_dropped"] += 1
    return out


def verify_paths(c: dict, ctx: ReportContext, fallback: Optional[Dict[str, List[str]]], corr: Counter) -> None:
    detail = c.get("detail") or {}
    for cat in detail.get("implementedFeatures") or []:
        for feat in (cat or {}).get("features") or []:
            feat["codeLocation"] = _verify_paths(feat.get("codeLocation"), ctx, corr)
            if not feat["codeLocation"] and fallback and fallback.get(feat.get("name")):
                feat["codeLocation"] = _verify_paths(fallback[feat["name"]], ctx, Counter())
                if feat["codeLocation"]:
                    corr["path_fallback"] += 1
    for ins in detail.get("codeInsights") or []:
        ins["codeLocation"] = _verify_paths(ins.get("codeLocation"), ctx, corr)


def filter_techstacks(techstacks, ctx: ReportContext, corr: Counter) -> List[str]:
    allowed = set(ctx.available_techstacks) - ROOT_TECHSTACKS
    out = []
    for t in techstacks or []:
        if t in allowed and t not in out:
            out.append(t)
        else:
            corr["enum_dropped"] += 1
    return out


def _collect(c: dict, path: str) -> List[tuple]:
    """경로에 해당하는 (부모 dict, 키) 목록."""
    holders = [c]
    parts = path.split(".")
    for i, part in enumerate(parts):
        last = i == len(parts) - 1
        key = part[:-2] if part.endswith("[]") else part
        nxt = []
        for h in holders:
            if not isinstance(h, dict):
                continue
            if last:
                nxt.append((h, key))
            elif part.endswith("[]"):
                nxt += [x for x in h.get(key) or [] if isinstance(x, dict)]
            else:
                nxt.append(h.get(key))
        holders = nxt
    return holders


def enforce_arrays(c: dict, corr: Counter) -> None:
    for path, (lo, hi) in ARRAY_LIMITS.items():
        for holder, key in _collect(c, path):
            arr = holder.get(key)
            if not isinstance(arr, list):
                continue
            if len(arr) > hi:
                corr["array_trimmed"] += len(arr) - hi
                holder[key] = arr[:hi]
            elif len(arr) < lo:
                corr["array_short"] += lo - len(arr)


def postprocess(
    raw: dict,
    raw_techstacks: List[str],
    ctx: ReportContext,
    tech_refs: Optional[dict] = None,
    fallback_locations: Optional[Dict[str, List[str]]] = None,
) -> PostprocessResult:
    c = copy.deepcopy(raw) if isinstance(raw, dict) else {}
    corr: Counter = Counter()
    fill_from_code(c, ctx)
    fill_versions(c, tech_refs, ctx, corr)
    renumber(c)
    verify_paths(c, ctx, fallback_locations, corr)
    techstacks = filter_techstacks(raw_techstacks, ctx, corr)
    enforce_arrays(c, corr)
    try:
        content = ReportContent.model_validate(c)
    except ValidationError as e:
        raise ReportGenerationError("contract_invalid", str(e)[:500], partial=c) from e
    if corr:
        logger.info(f"후처리 보정: {dict(corr)}")
    return PostprocessResult(content=content, techstacks=techstacks, corrections=dict(corr))
