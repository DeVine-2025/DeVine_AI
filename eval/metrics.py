"""결정론 지표(§9.1) + 기술적 가치 자동 지표(§9.3) 계산.

사용법:
    python -m eval.metrics eval/runs/2026-10-03 legacy_a legacy v1_adk [--embed]
"""
import argparse
import difflib
import hashlib
import json
import math
import os
import re
import statistics
import sys
from collections import Counter, defaultdict
from itertools import combinations

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

# 단가(USD / 1M 토큰). Q5: 공식 가격표로 재확인 필요. thinking 토큰은 output 단가.
PRICING = {
    "gemini-2.5-flash": {"input": 0.30, "cached": 0.03, "output": 2.50},
    "gemini-2.5-pro": {"input": 1.25, "cached": 0.125, "output": 10.0},
    "gemini-2.0-flash": {"input": 0.10, "cached": 0.025, "output": 0.40},
}
KRW_PER_USD = 1340
ROOT_TECHS = {"BACKEND", "FRONTEND", "INFRA"}
SIMILARITY_MATCH = 0.5
# text-embedding-3-small 기준 보정값(2026-10-03, A 18회): 일반론 쌍 0.73~0.80, 중앙값 0.60
GENERIC_COSINE = 0.72
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_.\-/]{2,}")

# 프롬프트가 요구한 배열 개수 (min, max)
ARRAY_RULES = {
    "main.overview.capabilities": (5, 5),
    "main.projectInfo.techStack": (5, 10),
    "main.keyImplementations": (4, 4),
    "main.keyImplementations[].capabilities": (4, 4),
    "main.aiEvaluation": (3, 3),
    "main.aiEvaluation[].details": (3, 3),
    "main.recommendations": (3, 3),
    "detail.implementedFeatures": (1, 5),
    "detail.implementedFeatures[].features": (2, 4),
    "detail.projectSummary.implemented": (3, 5),
    "detail.projectSummary.notImplemented": (0, 3),
    "detail.codeInsights": (4, 4),
    "detail.improvements": (3, 3),
    "detail.nextSteps": (3, 3),
}


CASE_FILTER: set[str] = set()  # 비어 있으면 전체. --cases로 부분집합 비교


def load_runs(base: str, engine: str) -> list[dict]:
    runs = []
    edir = os.path.join(base, engine)
    if not os.path.isdir(edir):
        return runs
    for case in sorted(os.listdir(edir)):
        cdir = os.path.join(edir, case)
        if not os.path.isdir(cdir) or (CASE_FILTER and case not in CASE_FILTER):
            continue
        for f in sorted(os.listdir(cdir), key=lambda x: int(x.split(".")[0]) if x[0].isdigit() else 0):
            if f.endswith(".json"):
                runs.append(json.load(open(os.path.join(cdir, f), encoding="utf-8")))
    return runs


def load_facts(base: str) -> dict:
    d = os.path.join(base, "_cases")
    facts = {}
    for f in os.listdir(d) if os.path.isdir(d) else []:
        data = json.load(open(os.path.join(d, f), encoding="utf-8"))
        data["head_set"] = set(data["head_files"])
        data["author_set"] = set(data["author_files"])
        data["ident_set"] = set(data["identifiers"])
        data["stem_set"] = {os.path.splitext(os.path.basename(p))[0] for p in data["head_files"] if len(os.path.splitext(os.path.basename(p))[0]) >= 4}
        data["dep_set"] = {d.lower() for d in data["dep_names"] if len(d) >= 3}
        facts[data["id"]] = data
    return facts


def _get(d, path):
    for key in path.split("."):
        if not isinstance(d, dict):
            return None
        d = d.get(key)
    return d


def code_locations(content: dict) -> list[str]:
    detail = (content or {}).get("detail", {}) or {}
    locs = []
    for cat in detail.get("implementedFeatures", []) or []:
        for feat in cat.get("features", []) or []:
            locs += [p for p in feat.get("codeLocation", []) or [] if isinstance(p, str)]
    for ins in detail.get("codeInsights", []) or []:
        locs += [p for p in ins.get("codeLocation", []) or [] if isinstance(p, str)]
    return locs


def _norm_path(p: str) -> str:
    """앞의 './', 줄 번호(:12, #L10), 뒤에 붙은 설명(' (...)', ' - ...')만 뗀다.
    점으로 시작하는 파일(.gitignore)과 Next.js 라우트 그룹 '(group)'은 경로의 일부이므로 남긴다."""
    p = p.strip().strip("`'\"").strip()
    p = re.sub(r"^\./", "", p).lstrip("/")
    return re.split(r"(?::\d|#L\d|\s\(|\s-\s)", p)[0].strip() if p else p


def path_validity(content: dict, facts: dict) -> tuple[int, int, int]:
    """(경로 수, HEAD에 있는 수, 작성자 수정 파일 수). 이름 변경 맵은 적용하지 않는다(원시 기준)."""
    locs = [_norm_path(p) for p in code_locations(content)]
    valid = sum(1 for p in locs if p in facts["head_set"])
    authored = sum(1 for p in locs if p in facts["author_set"])
    return len(locs), valid, authored


def array_violations(content: dict) -> int:
    count = 0
    for path, (lo, hi) in ARRAY_RULES.items():
        if "[]" in path:
            parent, child = path.split("[].")
            items = _get(content, parent) or []
            values = [it.get(child) for it in items if isinstance(it, dict)]
        else:
            values = [_get(content, path)]
        for v in values:
            n = len(v) if isinstance(v, list) else 0
            if not lo <= n <= hi:
                count += 1
    return count


def _norm_text(s: str) -> str:
    return re.sub(r"[\s()\[\]·,./\-]+", "", s or "").lower()


def consistency(content: dict) -> float | None:
    keys = [k.get("title", "") for k in (_get(content, "main.keyImplementations") or []) if isinstance(k, dict)]
    names = []
    for cat in _get(content, "detail.implementedFeatures") or []:
        names.append(cat.get("category", ""))
        names += [f.get("name", "") for f in cat.get("features", []) or []]
    if not keys or not names:
        return None
    hit = 0
    for k in keys:
        best = max(difflib.SequenceMatcher(None, _norm_text(k), _norm_text(n)).ratio() for n in names)
        hit += best >= SIMILARITY_MATCH
    return hit / len(keys)


def _items_text(content: dict, section: str) -> list[str]:
    out = []
    for it in _get(content, f"detail.{section}") or []:
        if isinstance(it, dict):
            parts = [str(v) if not isinstance(v, list) else " ".join(map(str, v)) for k, v in it.items() if k != "number"]
            out.append(" ".join(parts))
    return out


def concrete_ratio(content: dict, facts: dict) -> float | None:
    items = _items_text(content, "codeInsights") + _items_text(content, "improvements")
    if not items:
        return None
    hit = 0
    for text in items:
        toks = set(_IDENT.findall(text))
        toks |= {os.path.splitext(os.path.basename(t))[0] for t in toks}
        lower = {t.lower() for t in toks}
        if toks & facts["ident_set"] or toks & facts["stem_set"] or lower & facts["dep_set"] or any(p in text for p in facts["head_set"] if "/" in p):
            hit += 1
    return hit / len(items)


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a | b else 1.0


def feature_names(content: dict) -> set:
    names = set()
    for cat in _get(content, "detail.implementedFeatures") or []:
        names |= {_norm_text(f.get("name", "")) for f in cat.get("features", []) or []}
    return names


def cost_krw(usage: list[dict]) -> float:
    usd = 0.0
    for u in usage:
        price = PRICING.get(u.get("model", ""), PRICING["gemini-2.5-flash"])
        uncached = max(u.get("input", 0) - u.get("cached", 0), 0)
        usd += uncached * price["input"] / 1e6 + u.get("cached", 0) * price["cached"] / 1e6
        usd += (u.get("output", 0) + u.get("thinking", 0)) * price["output"] / 1e6
    return usd * KRW_PER_USD


def pct(values: list[float], q: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    k = (len(values) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    return values[lo] + (values[hi] - values[lo]) * (k - lo)


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return statistics.mean(xs) if xs else None


# ---- 일반론 비율(임베딩) ----

def _embed(texts: list[str], cache_path: str) -> dict[str, list[float]]:
    cache = json.load(open(cache_path)) if os.path.exists(cache_path) else {}
    missing = [t for t in set(texts) if hashlib.sha1(t.encode()).hexdigest() not in cache]
    if missing:
        from openai import OpenAI
        from app.configs.settings import settings

        client = OpenAI(api_key=settings.openai_api_key)
        for i in range(0, len(missing), 100):
            batch = missing[i:i + 100]
            resp = client.embeddings.create(model="text-embedding-3-small", input=batch)
            for t, d in zip(batch, resp.data):
                cache[hashlib.sha1(t.encode()).hexdigest()] = d.embedding
        json.dump(cache, open(cache_path, "w"))
    return {t: cache[hashlib.sha1(t.encode()).hexdigest()] for t in texts}


def _cos(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def generic_ratio(runs: list[dict], base: str, facts: dict) -> tuple[float | None, list[tuple[str, int]]]:
    """다른 레포 리포트에 거의 같은 항목이 있으면 일반론으로 센다. 같은 레포의 다른 시점 케이스끼리는 비교하지 않는다."""
    repo_of = {cid: f.get("repo_url") for cid, f in facts.items()}
    items = []  # (case, text, title)
    for r in runs:
        if not r.get("success"):
            continue
        for sec in ("improvements", "nextSteps"):
            for it in _get(r.get("content"), f"detail.{sec}") or []:
                title = it.get("title", "")
                body = " ".join(it.get("suggestions", []) or it.get("description", []) or [])
                items.append((r["case"], f"{title}: {body}"[:800], title))
    if len(items) < 2:
        return None, []
    emb = _embed([t for _, t, _ in items], os.path.join(base, "_embeddings.json"))
    generic = 0
    for case, text, _ in items:
        others = [t for c, t, _ in items if repo_of.get(c) != repo_of.get(case)]
        if others and max(_cos(emb[text], emb[o]) for o in others) >= GENERIC_COSINE:
            generic += 1
    common = Counter(_norm_text(t) for _, _, t in items).most_common(5)
    return generic / len(items), common


# ---- 요약 ----

def engine_summary(base: str, engine: str, facts: dict, embed: bool = False) -> dict:
    runs = load_runs(base, engine)
    positive = [r for r in runs if "negative" not in facts.get(r["case"], {}).get("tags", [])]
    negative = [r for r in runs if r not in positive]
    ok = [r for r in positive if r.get("success")]
    s: dict = {"runs": len(runs)}
    s["success_rate"] = len(ok) / len(positive) if positive else None
    s["negative_blocked"] = (sum(1 for r in negative if not r.get("success")) / len(negative)) if negative else None
    s["failure_reasons"] = dict(Counter(r.get("failure_reason") for r in runs if not r.get("success")))
    trouble = {"retry", "node_failed", "fallback", "fallback_skipped", "tech_degraded", "workflow_error", "model_error"}
    evented = [r for r in positive if any(e.get("type") in trouble for e in r.get("events", []))]
    s["recovered_rate"] = (sum(1 for r in evented if r.get("success")) / len(evented)) if evented else None
    s["fallback_rate"] = (sum(1 for r in positive if any(e.get("type") == "fallback" for e in r.get("events", []))) / len(positive)) if positive else None

    from app.report.contract import ReportContent

    contract_ok = 0
    for r in ok:
        try:
            ReportContent.model_validate(r["content"])
            contract_ok += 1
        except Exception:
            pass
    s["contract_pass"] = contract_ok / len(ok) if ok else None
    corr = defaultdict(list)
    for r in ok:
        for k, v in (r.get("corrections") or {}).items():
            corr[k].append(v)
    s["corrections_avg"] = {k: round(sum(v) / len(ok), 2) for k, v in sorted(corr.items())}
    s["array_violations_raw"] = _mean([array_violations(r.get("raw_content") or r.get("content")) for r in ok])
    s["enum_violations_raw"] = _mean([
        sum(1 for t in r.get("raw_techstacks", r.get("techstacks", [])) if t in ROOT_TECHS or not re.fullmatch(r"[A-Z_]+", str(t)))
        for r in ok
    ])

    tot = valid = authored = 0
    fin_tot = fin_auth = 0
    for r in ok:
        f = facts[r["case"]]
        n, v, _ = path_validity(r.get("raw_content") or r["content"], f)
        tot, valid = tot + n, valid + v
        n2, _, a2 = path_validity(r["content"], f)
        fin_tot, fin_auth = fin_tot + n2, fin_auth + a2
    s["raw_path_valid"] = valid / tot if tot else None
    s["attribution_hit"] = fin_auth / fin_tot if fin_tot else None
    s["codeLocation_per_report"] = fin_tot / len(ok) if ok else None
    s["consistency"] = _mean([consistency(r["content"]) for r in ok])

    by_case = defaultdict(list)
    for r in ok + [r for r in negative if r.get("success")]:
        by_case[r["case"]].append(r)
    jt, jf = [], []
    for case, rs in by_case.items():
        if "negative" in facts.get(case, {}).get("tags", []):
            continue
        for a, b in combinations(rs, 2):
            jt.append(jaccard(set(a.get("techstacks", [])), set(b.get("techstacks", []))))
            jf.append(jaccard(feature_names(a["content"]), feature_names(b["content"])))
    s["jaccard_techstacks"] = _mean(jt)
    s["jaccard_features"] = _mean(jf)

    s["tokens_avg"] = _mean([sum(u.get("input", 0) + u.get("output", 0) + u.get("thinking", 0) for u in r.get("usage", [])) for r in ok])
    s["input_tokens_avg"] = _mean([sum(u.get("input", 0) for u in r.get("usage", [])) for r in ok])
    s["krw_avg"] = _mean([cost_krw(r.get("usage", [])) for r in ok])
    s["calls_avg"] = _mean([len(r.get("usage", [])) for r in ok])
    times = [r["elapsed_ms"] / 1000 for r in ok]
    s["time_p50"], s["time_p95"] = pct(times, 0.5), pct(times, 0.95)
    s["concrete_ratio"] = _mean([concrete_ratio(r["content"], facts[r["case"]]) for r in ok])
    if embed:
        s["generic_ratio"], s["generic_common"] = generic_ratio(ok, base, facts)

    per_case = {}
    for case in sorted({r["case"] for r in runs}):
        all_rs = [r for r in runs if r["case"] == case]
        rs = by_case.get(case, [])
        if not rs:
            reasons = Counter(r.get("failure_reason") for r in all_rs)
            per_case[case] = {"ok": f"0/{len(all_rs)}", "time": round(_mean([r["elapsed_ms"] / 1000 for r in all_rs]), 1),
                              "input_tok": 0, "krw": 0.0, "path_valid": "-", "attrib": "-", "arr_viol": "-",
                              "note": ", ".join(f"{k}×{v}" for k, v in reasons.items())}
            continue
        if "negative" in facts.get(case, {}).get("tags", []):
            rs = [r for r in all_rs if r.get("success")]
        per_case[case] = {
            "ok": f"{len(rs)}/{len(all_rs)}",
            "time": round(_mean([r["elapsed_ms"] / 1000 for r in rs]), 1),
            "input_tok": int(_mean([sum(u.get("input", 0) for u in r.get("usage", [])) for r in rs])),
            "krw": round(_mean([cost_krw(r.get("usage", [])) for r in rs]), 1),
            "path_valid": _fmt(_ratio([path_validity(r.get("raw_content") or r["content"], facts[case]) for r in rs], 1)),
            "attrib": _fmt(_ratio([path_validity(r["content"], facts[case]) for r in rs], 2)),
            "arr_viol": round(_mean([array_violations(r.get("raw_content") or r["content"]) for r in rs]), 1),
            "note": "음성 케이스인데 리포트 생성" if "negative" in facts.get(case, {}).get("tags", []) else "",
        }
    s["per_case"] = per_case
    return s


def _ratio(triples, idx):
    tot = sum(t[0] for t in triples)
    return sum(t[idx] for t in triples) / tot if tot else None


def _fmt(v, digits=2):
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:.{digits}f}"
    return str(v)


ROWS = [
    ("성공률(양성 케이스)", "success_rate"), ("음성 케이스 차단율", "negative_blocked"), ("실패 사유", "failure_reasons"),
    ("복구율(이벤트 있는 실행 중 성공)", "recovered_rate"), ("폴백률", "fallback_rate"),
    ("계약 검증 통과율", "contract_pass"), ("보정 건수(평균)", "corrections_avg"),
    ("원시 배열 개수 위반(평균)", "array_violations_raw"), ("원시 techstacks 루트값/형식 위반(평균)", "enum_violations_raw"),
    ("원시 경로 유효율", "raw_path_valid"), ("귀속 적중률(최종)", "attribution_hit"), ("codeLocation 수/리포트", "codeLocation_per_report"),
    ("main↔detail 일치", "consistency"),
    ("반복 Jaccard techstacks", "jaccard_techstacks"), ("반복 Jaccard 기능명", "jaccard_features"),
    ("구체 참조율", "concrete_ratio"), ("일반론 비율", "generic_ratio"),
    ("입력 토큰/리포트", "input_tokens_avg"), ("총 토큰/리포트", "tokens_avg"), ("원화/리포트", "krw_avg"), ("LLM 호출 수", "calls_avg"),
    ("시간 p50(s)", "time_p50"), ("시간 p95(s)", "time_p95"), ("실행 수", "runs"),
]


def summarize(base: str, engines: list[str], embed: bool = False) -> str:
    facts = load_facts(base)
    sums = {e: engine_summary(base, e, facts, embed) for e in engines}
    lines = ["| 지표 | " + " | ".join(engines) + " |", "|---|" + "---|" * len(engines)]
    for label, key in ROWS:
        cells = []
        for e in engines:
            v = sums[e].get(key)
            if isinstance(v, dict):
                v = ", ".join(f"{k}={val}" for k, val in v.items()) or "-"
            elif isinstance(v, float) and key.startswith(("tokens", "input")):
                v = f"{v:,.0f}"
            elif isinstance(v, float) and key == "krw_avg":
                v = f"{v:.1f}"
            cells.append(_fmt(v))
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    for e in engines:
        lines += ["", f"**{e} 케이스별**", "", "| 케이스 | 성공 | 시간(s) | 입력 토큰 | 원화 | 원시 경로 유효 | 귀속 적중 | 배열 위반 | 비고 |", "|---|---|---|---|---|---|---|---|---|"]
        for case, pc in sums[e]["per_case"].items():
            lines.append(f"| {case} | {pc['ok']} | {pc['time']} | {pc['input_tok']:,} | {pc['krw']} | {pc['path_valid']} | {pc['attrib']} | {pc['arr_viol']} | {pc['note']} |")
        if sums[e].get("generic_common"):
            lines.append(f"\n자주 나온 improvements/nextSteps 제목({e}): " + ", ".join(f"{t}×{n}" for t, n in sums[e]["generic_common"]))
    return "\n".join(lines)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("base")
    p.add_argument("engines", nargs="+")
    p.add_argument("--embed", action="store_true")
    p.add_argument("--cases", default="", help="쉼표로 구분한 케이스 id만 집계")
    a = p.parse_args()
    CASE_FILTER.update(c for c in a.cases.split(",") if c)
    print(summarize(a.base, a.engines, a.embed))
