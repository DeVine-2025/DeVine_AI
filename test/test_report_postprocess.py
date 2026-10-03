import copy

import pytest

from app.report.context import ReportContext, ReportFacts
from app.report.errors import ReportGenerationError
from app.report.guards import check_guards
from app.report.postprocess import postprocess


def _ctx(**kw) -> ReportContext:
    base = dict(
        repo_url="https://github.com/o/DeVine_AI",
        project_name="DeVine_AI",
        author_name="heo",
        author_emails=["a@b.c"],
        available_techstacks=["BACKEND", "PYTHON", "DOCKER", "JAVA"],
        facts=ReportFacts(
            author_commit_count=5, author_added=12345, author_files_modified=17, author_period="약 3개월",
            project_code_files=40, project_code_lines=5000, project_period="약 8개월",
        ),
        head_files=["app/main.py", "app/services/git_service.py", "app/report/new_name.py"],
        rename_map={"app/old_name.py": "app/report/new_name.py"},
        build_versions={"fastapi": "0.141.1", "python": "3.11"},
    )
    base.update(kw)
    return ReportContext(**base)


def _raw() -> dict:
    feat = {"name": "Git 분석", "implementation": ["a", "b"], "codeLocation": ["app/services/git_service.py"], "details": ["x", "y"]}
    return {
        "main": {
            "overview": {"summary": "s", "mainTech": "Python", "capabilities": ["1", "2", "3", "4", "5"], "scale": "약 15,000줄 코드 작성"},
            "projectInfo": {"projectName": "wrong", "techStack": ["Python 3.9", "FastAPI", "Docker", "Gemini", "OpenAI"], "scale": "?"},
            "keyImplementations": [{"title": f"k{i}", "description": "d", "capabilities": ["a", "b", "c", "d"]} for i in range(4)],
            "aiEvaluation": [{"title": f"e{i}", "details": ["a", "b", "c"]} for i in range(3)],
            "recommendations": ["r1", "r2", "r3"],
        },
        "detail": {
            "reportTitle": "x",
            "reportSubtitle": "y",
            "projectOverview": {
                "purpose": "p",
                "techStack": [{"title": "백엔드", "content": "FastAPI"}],
                "projectScale": {"mainCodeFiles": 1, "totalCodeLines": 2, "developmentPeriod": "?", "architecturePattern": "계층형"},
            },
            "implementedFeatures": [
                {"category": "c1", "categoryNumber": 7, "features": [copy.deepcopy(feat), copy.deepcopy(feat)]},
            ],
            "projectSummary": {"implemented": ["a", "b", "c"], "notImplemented": []},
            "codeInsights": [{"number": 9, "title": f"i{i}", "points": ["a", "b"], "codeLocation": ["app/main.py"]} for i in range(4)],
            "improvements": [{"number": 1, "title": "t", "currentState": ["c"], "suggestions": ["s1", "s2"], "keywords": "k"} for _ in range(3)],
            "nextSteps": [{"number": 1, "title": "t", "description": ["d1", "d2"], "recommendKeyword": ["k1", "k2"]} for _ in range(3)],
        },
    }


def test_fills_numbers_from_code():
    res = postprocess(_raw(), ["PYTHON"], _ctx())
    d = res.content.to_legacy_dict()
    scale = d["detail"]["projectOverview"]["projectScale"]
    assert (scale["mainCodeFiles"], scale["totalCodeLines"], scale["developmentPeriod"]) == (40, 5000, "약 8개월")
    assert scale["architecturePattern"] == "계층형"
    assert d["main"]["overview"]["scale"] == "12,345줄 추가 · 17개 파일 수정 · 약 3개월 활동"
    assert d["main"]["projectInfo"]["scale"] == "5000줄 | 40개 파일 | 약 8개월 개발 기간"
    assert d["main"]["projectInfo"]["projectName"] == "DeVine_AI"
    assert d["detail"]["reportTitle"] == "DeVine_AI"
    assert d["detail"]["reportSubtitle"] == "프로젝트 상세 분석 리포트"


def test_renumbers():
    d = postprocess(_raw(), [], _ctx()).content.to_legacy_dict()["detail"]
    assert [c["categoryNumber"] for c in d["implementedFeatures"]] == [1]
    assert [i["number"] for i in d["codeInsights"]] == [1, 2, 3, 4]
    assert [i["number"] for i in d["improvements"]] == [1, 2, 3]


def test_paths_rename_drop_and_fallback():
    raw = _raw()
    feats = raw["detail"]["implementedFeatures"][0]["features"]
    feats[0]["codeLocation"] = ["./app/old_name.py", "src/ghost.py", "app/main.py:12", "app/services/"]
    feats[1]["codeLocation"] = ["nowhere.py"]
    res = postprocess(raw, [], _ctx(), fallback_locations={"Git 분석": ["app/main.py"]})
    out = res.content.to_legacy_dict()["detail"]["implementedFeatures"][0]["features"]
    assert out[0]["codeLocation"] == ["app/report/new_name.py", "app/main.py", "app/services/"]
    assert out[1]["codeLocation"] == ["app/main.py"]
    assert res.corrections["path_renamed"] == 1
    assert res.corrections["path_dropped"] == 2
    assert res.corrections["path_fallback"] == 1


def test_path_empty_without_fallback_stays_empty():
    raw = _raw()
    raw["detail"]["codeInsights"][0]["codeLocation"] = ["ghost.py"]
    res = postprocess(raw, [], _ctx())
    assert res.content.detail.codeInsights[0].codeLocation == []


def test_techstacks_filtered_to_enum_without_roots():
    res = postprocess(_raw(), ["PYTHON", "BACKEND", "FASTAPI", "PYTHON", "DOCKER"], _ctx())
    assert res.techstacks == ["PYTHON", "DOCKER"]
    assert res.corrections["enum_dropped"] == 3


def test_arrays_trimmed_and_short_counted_not_filled():
    raw = _raw()
    raw["main"]["overview"]["capabilities"] = [str(i) for i in range(7)]
    raw["main"]["recommendations"] = ["only one"]
    res = postprocess(raw, [], _ctx())
    assert len(res.content.main.overview.capabilities) == 5
    assert res.content.main.recommendations == ["only one"]
    assert res.corrections["array_trimmed"] == 2
    assert res.corrections["array_short"] == 2


def test_versions_filled_from_tech_refs():
    refs = {
        "projectInfo": [{"name": "Python 3.9", "dep": "python"}, {"name": "FastAPI", "dep": "fastapi"}, {"name": "Gemini", "dep": ""}],
        "overview": [{"title": "백엔드", "items": [{"name": "FastAPI", "dep": "fastapi"}, {"name": "Uvicorn", "dep": "uvicorn"}]}],
    }
    res = postprocess(_raw(), [], _ctx(), tech_refs=refs)
    assert res.content.main.projectInfo.techStack == ["Python 3.11", "FastAPI 0.141.1", "Gemini"]
    assert res.content.detail.projectOverview.techStack[0].content == "FastAPI 0.141.1, Uvicorn"
    assert res.corrections["version_filled"] == 3
    assert res.corrections["version_missing"] == 1


def test_contract_invalid_raises():
    raw = _raw()
    del raw["detail"]["nextSteps"]
    with pytest.raises(ReportGenerationError) as e:
        postprocess(raw, [], _ctx())
    assert e.value.reason == "contract_invalid"


def test_guard_blocks_zero_commits():
    ctx = _ctx(facts=ReportFacts(author_commit_count=0))
    with pytest.raises(ReportGenerationError) as e:
        check_guards(ctx)
    assert e.value.reason == "no_author_commits"


def test_guard_flags_low_evidence():
    ctx = _ctx(facts=ReportFacts(author_commit_count=2, author_added=10, author_deleted=3))
    assert check_guards(ctx) == ["low_evidence"]
    assert check_guards(_ctx()) == []
