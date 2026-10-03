from app.report.engines.base import EngineResult, ReportEngine


def get_engine(name: str) -> ReportEngine:
    if name == "legacy":
        from app.report.engines.legacy import LegacyEngine

        return LegacyEngine()
    raise ValueError(f"알 수 없는 리포트 엔진: {name}")


__all__ = ["EngineResult", "ReportEngine", "get_engine"]
