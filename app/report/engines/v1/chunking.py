"""V1 Map 입력: 파일·커밋 ID(S11)와 커밋 묶음 청크(Q2 1안).

- 파일 ID: 작성자가 건드린 HEAD 파일에 F1.., 다른 기여자 소유 파일에 O1..
- 커밋 ID: 작성자 커밋을 오래된 순으로 C1..
- 청크: 같은 날 연속 커밋을 한 묶음으로 보고, 묶음을 청크 토큰 상한까지 채운다.
  전체가 작으면 청크 1개(작은 레포 라우팅). 청크가 너무 많으면 diff 줄 상한을 줄인다.
"""
from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from app.report.context import ReportContext

CHARS_PER_TOKEN = 2.8
CHUNK_TOKENS = 20_000
SINGLE_CHUNK_TOKENS = 30_000
MAX_CHUNKS = 10
LINE_CAPS = (60, 30, 15, 8, 4)


def estimate_tokens(text: str) -> int:
    return int(len(text) / CHARS_PER_TOKEN) + 1


def _id_num(i: str) -> int:
    return int(i[1:])


@dataclass
class EvidenceIndex:
    file_ids: Dict[str, str] = field(default_factory=dict)  # F → HEAD 경로
    path_to_fid: Dict[str, str] = field(default_factory=dict)
    other_ids: Dict[str, str] = field(default_factory=dict)  # O → HEAD 경로
    commit_ids: Dict[str, str] = field(default_factory=dict)  # C → 해시
    hash_to_cid: Dict[str, str] = field(default_factory=dict)
    commit_meta: Dict[str, dict] = field(default_factory=dict)  # C → {date, message}


@dataclass
class Chunk:
    chunk_id: int
    commit_ids: List[str]
    file_ids: List[str]
    text: str


def head_path(ctx: ReportContext, path: str) -> str:
    if path in ctx.head_file_set:
        return path
    return ctx.rename_map.get(path, path)


def build_index(ctx: ReportContext, other_paths: List[str]) -> EvidenceIndex:
    idx = EvidenceIndex()
    author_paths = sorted({head_path(ctx, p) for p in ctx.file_changes} & ctx.head_file_set)
    for i, p in enumerate(author_paths, start=1):
        idx.file_ids[f"F{i}"] = p
        idx.path_to_fid[p] = f"F{i}"
    for i, p in enumerate(other_paths, start=1):
        idx.other_ids[f"O{i}"] = p
    # author_commits는 최신순이므로 뒤집은 뒤 안정 정렬하면 같은 시각일 때도 오래된 커밋이 앞선다
    for i, c in enumerate(sorted(reversed(ctx.author_commits), key=lambda c: c["date"]), start=1):
        cid = f"C{i}"
        idx.commit_ids[cid] = c["hash"]
        idx.hash_to_cid[c["hash"]] = cid
        idx.commit_meta[cid] = {"date": c["date"][:10], "message": c["message"]}
    return idx


def _commit_changes(ctx: ReportContext, idx: EvidenceIndex) -> Dict[str, List[Tuple[str, dict]]]:
    by_cid: Dict[str, List[Tuple[str, dict]]] = defaultdict(list)
    for path, data in ctx.file_changes.items():
        for ch in data["changes"]:
            cid = idx.hash_to_cid.get(ch.get("hash"))
            if cid:
                by_cid[cid].append((path, ch))
    return by_cid


def _render_commit(cid: str, idx: EvidenceIndex, changes: List[Tuple[str, dict]], ctx: ReportContext, cap: int) -> str:
    meta = idx.commit_meta[cid]
    out = [f"### {cid} | {meta['date']} | {meta['message']}"]
    for path, ch in sorted(changes, key=lambda x: x[0]):
        hp = head_path(ctx, path)
        fid = idx.path_to_fid.get(hp)
        if fid:
            label = f"[{fid}] {hp}" + (f" (당시 경로: {path})" if hp != path else "")
        else:
            label = f"{path} (HEAD에 없음)"
        out.append(f"--- {label}")
        added, deleted = ch.get("added") or [], ch.get("deleted") or []
        out += [f"+ {line}" for line in added[:cap]]
        if len(added) > cap:
            out.append(f"… (+{len(added) - cap}줄 생략)")
        dcap = max(cap // 2, 2)
        out += [f"- {line}" for line in deleted[:dcap]]
        if len(deleted) > dcap:
            out.append(f"… (-{len(deleted) - dcap}줄 생략)")
    return "\n".join(out)


def _pack(groups: List[List[Tuple[str, str]]], chunk_tokens: int) -> List[List[Tuple[str, str]]]:
    """묶음(같은 날 커밋들)을 청크 상한까지 채운다. 묶음 하나가 상한을 넘으면 커밋 단위로 나눈다."""
    chunks: List[List[Tuple[str, str]]] = []
    cur: List[Tuple[str, str]] = []
    cur_tok = 0
    for group in groups:
        g_tok = sum(estimate_tokens(t) for _, t in group)
        units = [group] if g_tok <= chunk_tokens else [[c] for c in group]
        for unit in units:
            u_tok = sum(estimate_tokens(t) for _, t in unit)
            if u_tok > chunk_tokens:  # 커밋 하나가 상한보다 크면 잘라 넣는다
                cid, text = unit[0]
                unit = [(cid, text[: int(chunk_tokens * CHARS_PER_TOKEN) - 50] + "\n… (커밋 diff 잘림)")]
                u_tok = chunk_tokens
            if cur and cur_tok + u_tok > chunk_tokens:
                chunks.append(cur)
                cur, cur_tok = [], 0
            cur += unit
            cur_tok += u_tok
    if cur:
        chunks.append(cur)
    return chunks


def build_chunks(
    ctx: ReportContext,
    idx: EvidenceIndex,
    chunk_tokens: int = CHUNK_TOKENS,
    single_chunk_tokens: int = SINGLE_CHUNK_TOKENS,
    max_chunks: int = MAX_CHUNKS,
) -> Tuple[List[Chunk], dict]:
    by_cid = _commit_changes(ctx, idx)
    cids = sorted(by_cid, key=_id_num)
    packed: List[List[Tuple[str, str]]] = []
    cap = LINE_CAPS[0]
    for cap in LINE_CAPS:
        texts = [(cid, _render_commit(cid, idx, by_cid[cid], ctx, cap)) for cid in cids]
        total = sum(estimate_tokens(t) for _, t in texts)
        if total <= single_chunk_tokens:
            packed = [texts]
            break
        days: "OrderedDict[str, list]" = OrderedDict()
        for cid, t in texts:
            days.setdefault(idx.commit_meta[cid]["date"], []).append((cid, t))
        packed = _pack(list(days.values()), chunk_tokens)
        if len(packed) <= max_chunks:
            break
    dropped = 0
    if len(packed) > max_chunks:
        keep = sorted(range(len(packed)), key=lambda i: -sum(len(t) for _, t in packed[i]))[:max_chunks]
        dropped = sum(len(packed[i]) for i in range(len(packed)) if i not in keep)
        packed = [packed[i] for i in sorted(keep)]

    chunks = []
    for n, items in enumerate(packed, start=1):
        text = "\n\n".join(t for _, t in items)
        fids = sorted({f for f in idx.file_ids if f"[{f}] " in text}, key=_id_num)
        chunks.append(Chunk(chunk_id=n, commit_ids=[c for c, _ in items], file_ids=fids, text=text))
    info = {
        "chunks": len(chunks),
        "line_cap": cap,
        "dropped_commits": dropped,
        "tokens": [estimate_tokens(c.text) for c in chunks],
    }
    return chunks, info
