from fastapi import APIRouter
from app.dtos.request_dto import ReportGenerationReq
from app.dtos.response_dto import ReportGenerationRes
from app.controllers.report_controller import report_controller

router = APIRouter()


@router.post("/generate", response_model=ReportGenerationRes)
async def generate_report(request: ReportGenerationReq):
    return await report_controller.generate_report(request)
