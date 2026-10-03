from app.report.engines.base import EngineResult, ReportEngine


def get_engine(name: str) -> ReportEngine:
    if name == "legacy":
        from app.report.engines.legacy import LegacyEngine

        return LegacyEngine()
    if name == "v1_adk":
        from app.report.engines.v1_adk import V1AdkEngine

        return V1AdkEngine()
    raise ValueError(f"알 수 없는 리포트 엔진: {name}")


__all__ = ["EngineResult", "ReportEngine", "get_engine"]
