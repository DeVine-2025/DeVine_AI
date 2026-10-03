"""평가 하네스: 케이스 × 엔진 × 반복 실행 → eval/runs/<날짜>/<engine>/<case>/<n>.json

사용법:
    python -m eval.run_eval --engine legacy_a --repeat 1
    python -m eval.run_eval --engine legacy --cases haru-web,devine-ai --repeat 3

엔진
- legacy_a: 기준선 A. 현재 analyzer 경로(_analyze_contributor)를 그대로 호출한다. 후처리 없음.
- 그 외: app.report.pipeline.generate_report(엔진 이름) 경로. 입력 수집 → 가드 → 엔진 → 후처리.
"""
import argparse
import asyncio
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import traceback

import yaml

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from eval.case_facts import compute_case_facts  # noqa: E402

CACHE = os.path.join(ROOT, "eval", ".cache")
RUNS = os.path.join(ROOT, "eval", "runs")


def _git(cwd: str, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout


def mirror_dir(repo_url: str) -> str:
    owner, repo = repo_url.rstrip("/").split("/")[-2:]
    path = os.path.join(CACHE, f"{owner}_{repo}")
    if not os.path.isdir(path):
        subprocess.run(["git", "clone", "-q", repo_url, path], check=True)
    return path


def prepare_workdir(case: dict) -> str:
    """미러에서 로컬 clone → SHA로 reset → origin 제거. 운영의 single-branch clone과 같은 상태를 만든다."""
    from app.services.git_service import create_mailmap

    work = os.path.join(CACHE, "work", case["id"])
    if not os.path.isdir(work):
        mirror = mirror_dir(case["repo_url"])
        subprocess.run(["git", "clone", "-q", "--no-hardlinks", mirror, work], check=True)
        _git(work, "reset", "-q", "--hard", str(case["sha"]))
        _git(work, "remote", "remove", "origin")
        for branch in _git(work, "for-each-ref", "--format=%(refname:short)", "refs/heads").split():
            if branch != _git(work, "rev-parse", "--abbrev-ref", "HEAD").strip():
                _git(work, "branch", "-D", branch)
    create_mailmap(work, case["author"]["name"], list(case["author"]["emails"]))
    return work


class UsageRecorder:
    """legacy_a 경로용: GeminiService._generate_content를 감싸 호출별 사용량을 모은다."""

    def __init__(self):
        self.records: list[dict] = []
        from app.services.gemini_service import GeminiService

        orig = GeminiService._generate_content
        recorder = self

        async def wrapped(self_, prompt, model_name):
            t0 = time.perf_counter()
            result, usage = await orig(self_, prompt, model_name)
            recorder.records.append(usage_record("single", model_name, usage, t0))
            return result, usage

        GeminiService._generate_content = wrapped


def usage_record(node: str, model: str, usage, t0: float) -> dict:
    return {
        "node": node,
        "model": model,
        "input": getattr(usage, "prompt_token_count", None) or 0,
        "cached": getattr(usage, "cached_content_token_count", None) or 0,
        "output": getattr(usage, "candidates_token_count", None) or 0,
        "thinking": getattr(usage, "thoughts_token_count", None) or 0,
        "ms": int((time.perf_counter() - t0) * 1000),
    }


async def run_legacy_a(case: dict, work: str, techstacks: list[str], recorder: UsageRecorder) -> dict:
    from app.services.analyzer_service import analyzer_service

    author = case["author"]
    start = len(recorder.records)
    result = await analyzer_service._analyze_contributor(
        work, case["repo_url"], author["name"], author["emails"][0], list(techstacks), list(author["emails"])
    )
    techs = result.pop("techstacks", []) if isinstance(result, dict) else []
    return {
        "content": result,
        "raw_content": result,
        "techstacks": techs,
        "corrections": {},
        "usage": recorder.records[start:],
        "events": [],
    }


async def run_engine(case: dict, work: str, techstacks: list[str], engine: str) -> dict:
    from app.report.pipeline import generate_report

    author = case["author"]
    outcome = await generate_report(
        dir_path=work,
        repo_url=case["repo_url"],
        author_name=author["name"],
        author_emails=list(author["emails"]),
        available_techstacks=list(techstacks),
        engine_name=engine,
    )
    return outcome.to_dict()


async def run_one(case, work, techstacks, engine, n, out_dir, recorder, sem):
    async with sem:
        t0 = time.perf_counter()
        record = {"case": case["id"], "engine": engine, "n": n, "started_at": dt.datetime.now().isoformat()}
        try:
            if engine == "legacy_a":
                res = await run_legacy_a(case, work, techstacks, recorder)
            else:
                res = await run_engine(case, work, techstacks, engine)
            record.update(res)
            record["success"] = True
            record["failure_reason"] = None
        except Exception as e:  # noqa: BLE001
            record["success"] = False
            record["failure_reason"] = getattr(e, "reason", None) or type(e).__name__
            record["error"] = str(e)[:2000]
            record["traceback"] = traceback.format_exc()[-3000:]
            partial = getattr(e, "outcome", None)
            if partial is not None:
                record.update({k: v for k, v in partial.to_dict().items() if k not in ("content",)})
        record["elapsed_ms"] = int((time.perf_counter() - t0) * 1000)
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, f"{n}.json"), "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=1, default=str)
        status = "OK " if record["success"] else f"FAIL({record['failure_reason']})"
        print(f"  [{engine}] {case['id']} #{n}: {status} {record['elapsed_ms'] / 1000:.1f}s", flush=True)


def code_version() -> dict:
    head = _git(ROOT, "rev-parse", "--short", "HEAD").strip()
    dirty = bool(_git(ROOT, "status", "--porcelain", "--untracked-files=no", "app").strip())
    prompt_files = []
    for d, _, files in os.walk(os.path.join(ROOT, "app")):
        prompt_files += [os.path.join(d, f) for f in files if f.endswith(".py") and ("prompt" in f or "prompt" in d)]
    h = hashlib.sha256()
    for p in sorted(prompt_files):
        h.update(open(p, "rb").read())
    return {"code_commit": head, "code_dirty": dirty, "prompt_hash": h.hexdigest()[:12]}


async def main_async(args):
    spec = yaml.safe_load(open(os.path.join(ROOT, "eval", "cases.yaml"), encoding="utf-8"))
    cases = spec["cases"]
    if args.cases:
        wanted = args.cases.split(",")
        cases = [c for c in cases if c["id"] in wanted]
    techstacks = spec["techstacks"]
    date = args.date or dt.date.today().isoformat()
    base = os.path.join(RUNS, date)
    recorder = UsageRecorder() if args.engine == "legacy_a" else None
    sem = asyncio.Semaphore(args.concurrency)
    thinking = "default"
    if args.engine not in ("legacy_a", "legacy"):
        import importlib

        thinking = getattr(importlib.import_module(f"app.report.engines.{args.engine}"), "THINKING_BUDGET", "default")
    meta = {"engine": args.engine, "model": "gemini-2.5-flash (fallback: 2.5-pro, 2.0-flash)", "temperature": "default",
            "thinking": thinking, **code_version()}

    tasks = []
    for case in cases:
        work = prepare_workdir(case)
        facts_path = os.path.join(base, "_cases", f"{case['id']}.json")
        if not os.path.exists(facts_path):
            os.makedirs(os.path.dirname(facts_path), exist_ok=True)
            facts = compute_case_facts(work, case["author"])
            facts.update({"id": case["id"], "repo_url": case["repo_url"], "sha": case["sha"], "tags": case.get("tags", [])})
            json.dump(facts, open(facts_path, "w", encoding="utf-8"), ensure_ascii=False)
        out_dir = os.path.join(base, args.engine, case["id"])
        existing = len([f for f in os.listdir(out_dir) if f.endswith(".json")]) if os.path.isdir(out_dir) else 0
        for n in range(existing + 1, existing + args.repeat + 1):
            tasks.append(run_one(case, work, techstacks, args.engine, n, out_dir, recorder, sem))
    os.makedirs(os.path.join(base, args.engine), exist_ok=True)
    json.dump(meta, open(os.path.join(base, args.engine, "_meta.json"), "w"), ensure_ascii=False, indent=1)
    print(f"실행: engine={args.engine} cases={len(cases)} runs={len(tasks)} → {base}", flush=True)
    await asyncio.gather(*tasks)

    from eval.metrics import summarize

    print(summarize(base, [args.engine]))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--engine", required=True)
    p.add_argument("--cases", default="")
    p.add_argument("--repeat", type=int, default=3)
    p.add_argument("--concurrency", type=int, default=1)
    p.add_argument("--date", default="", help="결과 폴더 날짜(기본 오늘). 같은 날짜에 이어 쓰면 회차 번호가 이어진다")
    p.add_argument("--fresh-workdir", action="store_true", help="케이스 작업 디렉터리를 다시 만든다")
    args = p.parse_args()
    if args.fresh_workdir:
        shutil.rmtree(os.path.join(CACHE, "work"), ignore_errors=True)
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
