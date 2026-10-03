from app.report.engines.shared.assemble import feature_locations
from app.report.engines.shared.evidence import VerifiedFeature
from app.report.engines.v1.ledger import FileOwnership, Ledger


def test_locations_prefer_source_over_stories_and_tests():
    paths = ["src/Button/Button.stories.tsx", "src/Button/Button.test.tsx", "src/Button/Button.tsx", "src/util.ts"]
    ledger = Ledger(files={p: FileOwnership(p, "created", 1.0, "me", 10, 10) for p in paths})
    ledger.files["src/util.ts"].level = "minor"
    f = VerifiedFeature(fid="K1", name="버튼", paths=paths)
    assert feature_locations(f, ledger) == ["src/Button/Button.tsx", "src/util.ts", "src/Button/Button.stories.tsx"]
