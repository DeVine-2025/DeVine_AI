from fastapi import APIRouter
from app.dtos.request_dto import ReportGenerationReq, ReportGenerationSyncReq
from app.dtos.response_dto import ReportGenerationRes, ReportGenerationSyncRes
from app.controllers.report_controller import report_controller

router = APIRouter()


@router.post("/generate", response_model=ReportGenerationRes)
async def generate_report(request: ReportGenerationReq):
    return await report_controller.generate_report(request)


@router.post("/generate/sync", response_model=ReportGenerationSyncRes)
async def generate_report_v2(request: ReportGenerationSyncReq) -> ReportGenerationSyncRes:
    """동기식 리포트 생성 - 분석 완료 후 결과 직접 반환"""
    return await report_controller.generate_report_sync(request)
