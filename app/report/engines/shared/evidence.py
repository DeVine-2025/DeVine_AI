"""근거 검증·병합 (V1 카드 병합, V3 N2 공용).

- 파일 ID를 HEAD 경로로 바꾸고, 유효한 파일이 하나도 없는 기능은 버린다.
- 이름이 비슷하거나 근거 파일이 많이 겹치는 기능은 하나로 합친다(청크마다 같은 기능이 나올 수 있음).
- 기여 수준은 LLM 힌트가 아니라 기여 원장(코드 계산)으로 정한다.
- 근거가 많은 순으로 K1..을 붙인다. 뒤 단계 LLM은 이 ID로만 기능을 가리킨다.
"""
import difflib
import re
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

LEVEL_RANK = {"created": 0, "major": 1, "minor": 2}
NAME_SIMILARITY = 0.75
FILE_JACCARD = 0.5
MAX_FEATURES = 25


@dataclass
class VerifiedFeature:
    fid: str
    name: str
    summaries: List[str] = field(default_factory=list)
    paths: List[str] = field(default_factory=list)
    file_ids: List[str] = field(default_factory=list)
    commit_ids: List[str] = field(default_factory=list)
    level: str = "minor"


def _norm(s: str) -> str:
    return re.sub(r"[\s()\[\]·,./\-_]+", "", s or "").lower()


def _similar(a: VerifiedFeature, b: VerifiedFeature) -> bool:
    if difflib.SequenceMatcher(None, _norm(a.name), _norm(b.name)).ratio() >= NAME_SIMILARITY:
        return True
    fa, fb = set(a.paths), set(b.paths)
    return bool(fa and fb) and len(fa & fb) / len(fa | fb) >= FILE_JACCARD


def _add_unique(dst: list, items) -> None:
    for it in items:
        if it not in dst:
            dst.append(it)


def verify_and_merge(cards: List[dict], idx, ledger, max_features: int = MAX_FEATURES, merge: bool = True) -> Tuple[List[VerifiedFeature], Dict[str, int]]:
    stats = {"card_features": 0, "dropped_no_file": 0, "merged": 0, "invalid_ids": 0}
    feats: List[VerifiedFeature] = []
    for card in cards:
        for cf in (card or {}).get("features", []) or []:
            stats["card_features"] += 1
            fids = []
            for fid in cf.get("file_ids") or []:
                if fid in idx.file_ids:
                    _add_unique(fids, [fid])
                else:
                    stats["invalid_ids"] += 1
            if not fids:
                stats["dropped_no_file"] += 1
                continue
            cids = [c for c in cf.get("commit_ids") or [] if c in idx.commit_ids]
            cand = VerifiedFeature(
                fid="",
                name=(cf.get("name") or "").strip(),
                summaries=[cf["summary"]] if cf.get("summary") else [],
                paths=[idx.file_ids[f] for f in fids],
                file_ids=fids,
                commit_ids=cids,
            )
            target = next((f for f in feats if merge and _similar(f, cand)), None)
            if target is None:
                feats.append(cand)
                continue
            stats["merged"] += 1
            _add_unique(target.summaries, cand.summaries)
            _add_unique(target.paths, cand.paths)
            _add_unique(target.file_ids, cand.file_ids)
            _add_unique(target.commit_ids, cand.commit_ids)

    for f in feats:
        levels = [ledger.files[p].level for p in f.paths if p in ledger.files]
        f.level = min(levels, key=LEVEL_RANK.get) if levels else "minor"
        f.summaries = f.summaries[:3]
        f.commit_ids.sort(key=lambda c: int(c[1:]))

    feats.sort(key=lambda f: (-(len(f.commit_ids) + len(f.paths)), LEVEL_RANK[f.level]))
    feats = feats[:max_features]
    for i, f in enumerate(feats, start=1):
        f.fid = f"K{i}"
    return feats, stats
