from app.report.context import ReportContext
from app.report.engines.v1.chunking import build_chunks, build_index, estimate_tokens


def _ctx(n_commits=6, lines=10, line_len=40, same_day=2):
    file_changes = {}
    commits = []
    for i in range(n_commits):
        h = f"{i:040d}"
        date = f"2025-07-{1 + i // same_day:02d}"
        commits.append({"hash": h, "date": date + "T10:00:00", "message": f"feat: change {i}"})
        for f in (f"src/mod{i % 3}.ts", "src/gone.ts"):
            fc = file_changes.setdefault(f, {"commits": 0, "totalAdded": 0, "totalDeleted": 0, "changes": []})
            fc["commits"] += 1
            fc["changes"].append({"hash": h, "date": date, "message": f"feat: change {i}",
                                  "added": ["x" * line_len] * lines, "deleted": ["y" * line_len] * 2})
    return ReportContext(
        repo_url="u", project_name="p", author_name="a", author_emails=["a@x"],
        author_commits=list(reversed(commits)), file_changes=file_changes,
        head_files=["src/mod0.ts", "src/mod1.ts", "src/mod2.ts", "README.md"],
    )


def test_index_assigns_ids_to_head_files_only():
    idx = build_index(_ctx(), other_paths=["README.md"])
    assert set(idx.file_ids.values()) == {"src/mod0.ts", "src/mod1.ts", "src/mod2.ts"}
    assert idx.path_to_fid["src/mod0.ts"] == "F1"
    assert idx.other_ids == {"O1": "README.md"}
    assert idx.commit_ids["C1"] == "0" * 40  # 가장 오래된 커밋이 C1


def test_small_input_is_single_chunk_with_ids_in_text():
    ctx = _ctx()
    idx = build_index(ctx, [])
    chunks, info = build_chunks(ctx, idx)
    assert len(chunks) == 1
    c = chunks[0]
    assert c.file_ids == ["F1", "F2", "F3"]
    assert c.commit_ids == [f"C{i}" for i in range(1, 7)]
    assert "[F1] src/mod0.ts" in c.text and "src/gone.ts (HEAD에 없음)" in c.text
    assert info["line_cap"] >= 10


def test_large_input_splits_by_day_groups_under_budget():
    ctx = _ctx(n_commits=40, lines=200, line_len=60, same_day=4)
    idx = build_index(ctx, [])
    chunks, info = build_chunks(ctx, idx, chunk_tokens=8000, single_chunk_tokens=10000, max_chunks=12)
    assert 1 < len(chunks) <= 12
    assert all(estimate_tokens(c.text) <= 8000 * 1.05 for c in chunks)
    # 같은 날 커밋은 같은 청크에 있다
    day_of = {}
    for c in chunks:
        for cid in c.commit_ids:
            day = (int(cid[1:]) - 1) // 4
            day_of.setdefault(day, set()).add(c.chunk_id)
    assert all(len(s) == 1 for s in day_of.values())
    covered = sorted(int(cid[1:]) for c in chunks for cid in c.commit_ids)
    assert covered == list(range(1, 41))


def test_over_budget_reduces_line_cap_then_drops():
    ctx = _ctx(n_commits=40, lines=400, line_len=80, same_day=1)
    idx = build_index(ctx, [])
    chunks, info = build_chunks(ctx, idx, chunk_tokens=3000, single_chunk_tokens=3000, max_chunks=4)
    assert len(chunks) <= 4
    assert info["line_cap"] < 60
    assert info["dropped_commits"] >= 0
