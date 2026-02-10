import asyncio
from app.dtos.request_dto import ReportGenerationReq, ReportGenerationSyncReq
from app.dtos.response_dto import ReportGenerationRes, ReportGenerationSyncRes
from app.services.analyzer_service import analyzer_service


class ReportController:
    async def generate_report(self, request: ReportGenerationReq) -> ReportGenerationRes:
        asyncio.create_task(analyzer_service.analyze_and_callback(request))

        return ReportGenerationRes(
            detailReportId=request.detailReportId,
            mainReportId=request.mainReportId,
            status="ACCEPTED",
            message="리포트 생성 요청이 접수되었습니다."
        )

    async def generate_report_sync(self, request: ReportGenerationSyncReq) -> ReportGenerationSyncRes:
        result = await analyzer_service.analyze_sync(request)

        return ReportGenerationSyncRes(
            mainReportId=request.mainReportId,
            detailReportId=request.detailReportId,
            status=result["status"],
            content=result["content"],
            errorMessage=result["errorMessage"],
            techstacks=result.get("techstacks", [])
        )


report_controller = ReportController()
