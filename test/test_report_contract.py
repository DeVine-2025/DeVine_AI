from app.report.contract import ReportContent
from app.services.gemini_service import _REPORT_SCHEMA

_TYPE_ALIASES = {"integer": "number"}


def _resolve(schema: dict, defs: dict) -> dict:
    if "$ref" in schema:
        return defs[schema["$ref"].split("/")[-1]]
    return schema


def _flatten(schema: dict, defs: dict, path: str = "") -> dict:
    schema = _resolve(schema, defs)
    t = _TYPE_ALIASES.get(schema.get("type"), schema.get("type"))
    out = {path or "$": t}
    if t == "object":
        for key, sub in schema.get("properties", {}).items():
            out.update(_flatten(sub, defs, f"{path}.{key}"))
        out[f"{path or '$'}#required"] = tuple(sorted(schema.get("required", [])))
    elif t == "array":
        out.update(_flatten(schema["items"], defs, f"{path}[]"))
    return out


def test_contract_matches_legacy_schema_paths_and_types():
    legacy = {k: v for k, v in _REPORT_SCHEMA["properties"].items() if k != "techstacks"}
    legacy_schema = {"type": "object", "properties": legacy, "required": ["main", "detail"]}
    model_schema = ReportContent.model_json_schema()

    expected = _flatten(legacy_schema, {})
    actual = _flatten(model_schema, model_schema.get("$defs", {}))

    assert actual == expected


def _sample() -> dict:
    return {
        "main": {
            "overview": {"summary": "s", "mainTech": "t", "capabilities": ["a"], "scale": "x"},
            "projectInfo": {"projectName": "p", "techStack": ["Java 17"], "scale": "x"},
            "keyImplementations": [{"title": "k", "description": "d", "capabilities": ["c"]}],
            "aiEvaluation": [{"title": "e", "details": ["d"]}],
            "recommendations": ["r"],
        },
        "detail": {
            "reportTitle": "p",
            "reportSubtitle": "프로젝트 상세 분석 리포트",
            "projectOverview": {
                "purpose": "p",
                "techStack": [{"title": "백엔드", "content": "Spring"}],
                "projectScale": {"mainCodeFiles": 3, "totalCodeLines": 100, "developmentPeriod": "약 1개월", "architecturePattern": "계층"},
            },
            "implementedFeatures": [
                {"category": "c", "categoryNumber": 1.0, "features": [{"name": "n", "implementation": ["i"], "codeLocation": ["a.py"], "details": ["d"]}]}
            ],
            "projectSummary": {"implemented": ["i"], "notImplemented": []},
            "codeInsights": [{"number": 1, "title": "t", "points": ["p"], "codeLocation": ["a.py"]}],
            "improvements": [{"number": 1, "title": "t", "currentState": ["c"], "suggestions": ["s"], "keywords": "k"}],
            "nextSteps": [{"number": 1, "title": "t", "description": ["d"], "recommendKeyword": ["k"]}],
        },
    }


def test_legacy_response_validates_and_round_trips():
    content = ReportContent.model_validate(_sample())
    out = content.to_legacy_dict()
    assert out["detail"]["implementedFeatures"][0]["categoryNumber"] == 1
    assert set(out) == {"main", "detail"}
