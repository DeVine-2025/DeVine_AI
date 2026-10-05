from app.report.engines.shared.evidence import verify_and_merge
from app.report.engines.v1.chunking import EvidenceIndex
from app.report.engines.v1.ledger import FileOwnership, Ledger


def _idx():
    files = {"F1": "src/login.ts", "F2": "src/signup.ts", "F3": "src/util.ts"}
    return EvidenceIndex(file_ids=files, path_to_fid={v: k for k, v in files.items()},
                         commit_ids={"C1": "h1", "C2": "h2", "C3": "h3"})


def _ledger():
    return Ledger(files={
        "src/login.ts": FileOwnership("src/login.ts", "created", 0.9, "me", 90, 100),
        "src/signup.ts": FileOwnership("src/signup.ts", "minor", 0.1, "bob", 5, 50),
        "src/util.ts": FileOwnership("src/util.ts", "major", 0.6, "bob", 30, 50),
    })


def test_merge_by_name_and_files_and_drop_without_files():
    cards = [
        {"features": [
            {"name": "로그인 API", "summary": "JWT 발급", "file_ids": ["F1"], "commit_ids": ["C1"]},
            {"name": "근거 없는 기능", "summary": "x", "file_ids": [], "commit_ids": ["C2"]},
        ]},
        {"features": [
            {"name": "로그인 API 구현", "summary": "토큰 갱신", "file_ids": ["F1", "F3"], "commit_ids": ["C2"]},
            {"name": "회원가입 화면", "summary": "폼 검증", "file_ids": ["F2", "F9"], "commit_ids": ["C3"]},
        ]},
    ]
    feats, stats = verify_and_merge(cards, _idx(), _ledger())
    assert [f.name for f in feats] == ["로그인 API", "회원가입 화면"]
    login, signup = feats
    assert login.fid == "K1" and login.paths == ["src/login.ts", "src/util.ts"]
    assert login.summaries == ["JWT 발급", "토큰 갱신"] and login.commit_ids == ["C1", "C2"]
    assert login.level == "created"
    assert signup.level == "minor" and signup.paths == ["src/signup.ts"]
    assert stats == {"card_features": 4, "dropped_no_file": 1, "merged": 1, "invalid_ids": 1}


def test_cap_keeps_strongest_evidence():
    cards = [{"features": [
        {"name": f"기능{i}", "summary": "s", "file_ids": ["F1"] if i else ["F1", "F2", "F3"], "commit_ids": ["C1"]}
        for i in range(5)]}]
    feats, _ = verify_and_merge(cards, _idx(), _ledger(), max_features=1, merge=False)
    assert [f.name for f in feats] == ["기능0"]
