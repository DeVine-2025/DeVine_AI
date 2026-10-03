"""V1 실행별 단계 분해: 청크 수, Map 실패, 카드 병합, 단계별 지연(최대값), 노드별 토큰, 폴백·재시도.

사용법: python -m eval.v1_breakdown eval/runs/2026-10-03 [engine]
"""
import statistics
import sys
from collections import Counter, defaultdict

from eval.metrics import load_runs


def stage_of(node: str) -> str:
    return "map" if node.startswith("map_") else node


def main(base: str, engine: str = "v1_adk") -> None:
    runs = load_runs(base, engine)
    print("| 케이스 | # | 성공 | 총(s) | 청크 | Map 실패 | 카드 기능→병합 후 | Map(s) | tech(s) | features(s) | insights(s) | main(s) | 호출 | 이벤트 |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    stage_ms = defaultdict(list)
    tokens = defaultdict(lambda: defaultdict(int))
    event_types = Counter()
    for r in runs:
        ev = {e["type"]: e for e in r.get("events", [])}
        per = defaultdict(int)
        for u in r.get("usage", []):
            s = stage_of(u["node"])
            per[s] = max(per[s], u.get("ms") or 0)
            for k in ("input", "output", "thinking"):
                tokens[s][k] += u.get(k, 0)
        for s, v in per.items():
            stage_ms[s].append(v)
        event_types.update(e["type"] for e in r.get("events", []) if e["type"] not in ("chunks", "map_done", "verify", "assemble"))
        ch, md, vf = ev.get("chunks", {}), ev.get("map_done", {}), ev.get("verify", {})
        others = [e["type"] for e in r.get("events", []) if e["type"] not in ("chunks", "map_done", "verify", "assemble")]
        print(f"| {r['case']} | {r['n']} | {'O' if r.get('success') else r.get('failure_reason')} | {r['elapsed_ms'] / 1000:.1f} | "
              f"{ch.get('usable', '-')} | {md.get('failed', '-')} | {vf.get('card_features', '-')}→{vf.get('features', '-')} | "
              + " | ".join(f"{per.get(s, 0) / 1000:.1f}" for s in ("map", "tech", "features", "insights", "main"))
              + f" | {len(r.get('usage', []))} | {', '.join(others) or '-'} |")
    print("\n단계별 지연 중앙값(s):", {s: round(statistics.median(v) / 1000, 1) for s, v in stage_ms.items()})
    n = len([r for r in runs if r.get("usage")]) or 1
    print("단계별 평균 토큰(리포트당):", {s: {k: v // n for k, v in t.items()} for s, t in tokens.items()})
    print("이벤트 합계:", dict(event_types))


if __name__ == "__main__":
    main(*sys.argv[1:])
