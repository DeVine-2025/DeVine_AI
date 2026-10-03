"""섹션 결과 → 계약 구조 dict. 코드로 채우는 필드(규모·이름 등)는 빈 값으로 두고 후처리가 채운다."""
import re
from typing import Dict, List, Optional, Tuple

from app.report.engines.shared.evidence import LEVEL_RANK, VerifiedFeature
from app.report.engines.shared.schemas import NO_DEP

MAX_LOCATIONS = 3
_AUX = re.compile(r"(\.stories\.|\.test\.|\.spec\.|__tests__/|/tests?/|\.d\.ts$)")


def feature_locations(feat: VerifiedFeature, ledger) -> List[str]:
    """기능 근거 경로 중 최대 3개. 소스 파일(스토리·테스트 아님) → 작성자 몫이 큰 순."""
    def key(p):
        aux = bool(_AUX.search(p))
        own = ledger.files.get(p)
        if not own:
            return (aux, 3, 0.0)
        share = own.blame_share if own.blame_share is not None else own.author_share
        return (aux, LEVEL_RANK[own.level], -share)

    return sorted(feat.paths, key=key)[:MAX_LOCATIONS]


def detail_view(features: dict, insights: dict, feats_by_fid: Dict[str, VerifiedFeature]) -> dict:
    """Main 에이전트 입력용: detail을 사람이 읽는 형태로(fid와 수준 포함, 경로 제외)."""
    cats = []
    for cat in features.get("categories", []):
        cats.append({
            "category": cat.get("category"),
            "features": [
                {"fid": f.get("fid"), "level": feats_by_fid[f["fid"]].level if f.get("fid") in feats_by_fid else "minor",
                 "name": f.get("name"), "implementation": f.get("implementation"), "details": f.get("details")}
                for f in cat.get("features", [])
            ],
        })
    return {
        "purpose": features.get("purpose"),
        "implementedFeatures": cats,
        "implemented": features.get("implemented"),
        "notImplemented": [n.get("text") for n in features.get("notImplemented", [])],
        "architecturePattern": insights.get("architecturePattern"),
        "codeInsights": [{"title": i.get("title"), "points": i.get("points")} for i in insights.get("codeInsights", [])],
        "improvements": [{"title": i.get("title"), "currentState": i.get("currentState")} for i in insights.get("improvements", [])],
    }


def assemble(
    features: dict,
    insights: dict,
    main: dict,
    tech: Optional[dict],
    feats_by_fid: Dict[str, VerifiedFeature],
    ledger,
    idx,
) -> Tuple[dict, List[str], Optional[dict], Dict[str, List[str]], Dict[str, int]]:
    """(content, techstacks, tech_refs, fallback_locations, stats)"""
    stats = {"duplicate_fid": 0, "unknown_fid": 0}
    seen = set()
    categories = []
    fallback: Dict[str, List[str]] = {}
    for cat in features.get("categories", []):
        out_feats = []
        for f in cat.get("features", []):
            vf = feats_by_fid.get(f.get("fid"))
            if vf is None:
                stats["unknown_fid"] += 1
                continue
            if vf.fid in seen:
                stats["duplicate_fid"] += 1
                continue
            seen.add(vf.fid)
            locs = feature_locations(vf, ledger)
            fallback[f.get("name", vf.name)] = locs
            out_feats.append({
                "name": f.get("name") or vf.name,
                "implementation": f.get("implementation", []),
                "codeLocation": locs,
                "details": f.get("details", []),
            })
        if out_feats:
            categories.append({"category": cat.get("category", ""), "categoryNumber": 0, "features": out_feats})

    insights_out = [
        {"number": 0, "title": i.get("title", ""), "points": i.get("points", []),
         "codeLocation": [idx.file_ids[f] for f in i.get("file_ids", []) if f in idx.file_ids]}
        for i in insights.get("codeInsights", [])
    ]
    key_impls = [
        {"title": k.get("title", ""), "description": k.get("description", ""), "capabilities": k.get("capabilities", [])}
        for k in main.get("keyImplementations", [])
    ]
    tech_refs = None
    techstacks: List[str] = []
    if tech:
        techstacks = list(tech.get("techstacks", []))
        def refs(items):
            return [{"name": it.get("name", ""), "dep": "" if it.get("dep") == NO_DEP else it.get("dep", "")} for it in items]

        tech_refs = {
            "projectInfo": refs(tech.get("projectTech", [])),
            "overview": [{"title": g.get("title", ""), "items": refs(g.get("items", []))} for g in tech.get("overviewGroups", [])],
        }

    content = {
        "main": {
            "overview": {"summary": main.get("summary", ""), "mainTech": main.get("mainTech", ""),
                         "capabilities": main.get("capabilities", []), "scale": ""},
            "projectInfo": {"projectName": "", "techStack": [], "scale": ""},
            "keyImplementations": key_impls,
            "aiEvaluation": main.get("aiEvaluation", []),
            "recommendations": main.get("recommendations", []),
        },
        "detail": {
            "reportTitle": "",
            "reportSubtitle": "",
            "projectOverview": {
                "purpose": features.get("purpose", ""),
                "techStack": [],
                "projectScale": {"mainCodeFiles": 0, "totalCodeLines": 0, "developmentPeriod": "",
                                 "architecturePattern": insights.get("architecturePattern", "")},
            },
            "implementedFeatures": categories,
            "projectSummary": {
                "implemented": features.get("implemented", []),
                "notImplemented": [n.get("text", "") for n in features.get("notImplemented", []) if n.get("file_id") in idx.other_ids],
            },
            "codeInsights": insights_out,
            "improvements": [{"number": 0, **{k: i.get(k) for k in ("title", "currentState", "suggestions", "keywords")}}
                             for i in insights.get("improvements", [])],
            "nextSteps": [{"number": 0, **{k: n.get(k) for k in ("title", "description", "recommendKeyword")}}
                          for n in insights.get("nextSteps", [])],
        },
    }
    return content, techstacks, tech_refs, fallback, stats
