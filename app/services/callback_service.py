import httpx
from typing import Any, Optional, List
from app.configs.settings import settings
from app.dtos.response_dto import CallbackReq, EmbeddingCallbackReq
from app.errors.exceptions import CallbackException


class CallbackService:
    def __init__(self):
        self.timeout = 30.0
        self._headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + settings.internal_api_key,
        }

    async def send_callback(
        self,
        callback_url: str,
        detail_report_id: int,
        main_report_id: int,
        status: str,
        content: Optional[Any] = None,
        error_message: Optional[str] = None,
        techstacks: Optional[List[str]] = None
    ):
        payload = CallbackReq(
            detailReportId=detail_report_id,
            mainReportId=main_report_id,
            status=status,
            content=content,
            errorMessage=error_message,
            techstacks=techstacks
        )

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    callback_url,
                    json=payload.model_dump(),
                    headers=self._headers
                )

                if response.status_code >= 400:
                    raise CallbackException(f"콜백 전송 실패: HTTP {response.status_code}")

        except httpx.TimeoutException:
            raise CallbackException("콜백 전송 시간 초과")
        except httpx.RequestError as e:
            raise CallbackException(f"콜백 전송 중 오류: {str(e)}")

    async def send_success(
        self,
        callback_url: str,
        detail_report_id: int,
        main_report_id: int,
        content: Any,
        techstacks: Optional[List[str]] = None
    ):
        await self.send_callback(
            callback_url=callback_url,
            detail_report_id=detail_report_id,
            main_report_id=main_report_id,
            status="SUCCESS",
            content=content,
            techstacks=techstacks
        )

    async def send_failure(self, callback_url: str, detail_report_id: int, main_report_id: int, error_message: str):
        await self.send_callback(
            callback_url=callback_url,
            detail_report_id=detail_report_id,
            main_report_id=main_report_id,
            status="FAILED",
            error_message=error_message
        )

    async def send_embedding_callback(
        self,
        callback_url: str,
        detail_report_id: int,
        main_report_id: int,
        status: str,
        vector: Optional[List[float]] = None,
        dimension: Optional[int] = None,
        error_message: Optional[str] = None
    ):
        payload = EmbeddingCallbackReq(
            detailReportId=detail_report_id,
            mainReportId=main_report_id,
            status=status,
            vector=vector,
            dimension=dimension,
            errorMessage=error_message
        )

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    callback_url,
                    json=payload.model_dump(),
                    headers=self._headers
                )

                if response.status_code >= 400:
                    raise CallbackException(f"임베딩 콜백 전송 실패: HTTP {response.status_code}")

        except httpx.TimeoutException:
            raise CallbackException("임베딩 콜백 전송 시간 초과")
        except httpx.RequestError as e:
            raise CallbackException(f"임베딩 콜백 전송 중 오류: {str(e)}")

    async def send_embedding_success(
        self,
        callback_url: str,
        detail_report_id: int,
        main_report_id: int,
        vector: List[float],
        dimension: int
    ):
        await self.send_embedding_callback(
            callback_url=callback_url,
            detail_report_id=detail_report_id,
            main_report_id=main_report_id,
            status="SUCCESS",
            vector=vector,
            dimension=dimension
        )

    async def send_embedding_failure(
        self,
        callback_url: str,
        detail_report_id: int,
        main_report_id: int,
        error_message: str
    ):
        await self.send_embedding_callback(
            callback_url=callback_url,
            detail_report_id=detail_report_id,
            main_report_id=main_report_id,
            status="FAILED",
            error_message=error_message
        )


callback_service = CallbackService()
