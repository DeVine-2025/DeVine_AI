import asyncio
import logging
import time
from typing import Union

from app.dtos.request_dto import ReportGenerationReq, ReportGenerationSyncReq
from app.services.git_service import (
    clone_repository,
    cleanup_directory,
    create_mailmap,
    get_github_user_from_token,
    get_user_author_identities_from_github,
    parse_repo_url
)
from app.configs.settings import settings
from app.services.callback_service import callback_service
from app.services.embedding_service import embedding_service
from app.utils.text_processor import extract_embedding_text
from app.report.pipeline import ReportOutcome, generate_report
from app.errors.exceptions import AuthorMatchException

logger = logging.getLogger(__name__)


class AnalyzerService:
    def _clone_and_get_user_info(
        self, request: Union[ReportGenerationReq, ReportGenerationSyncReq], log_prefix: str
    ) -> tuple:
        """GitHub 신원 조회 → clone → .mailmap 생성. (author_name, author_emails, temp_dir)"""
        author_name, author_email = get_github_user_from_token(request.githubToken)
        author_emails = list(request.authorEmails) if request.authorEmails else [author_email]
        logger.info(f"{log_prefix} 분석 대상: {author_name} ({author_email}), 이메일 목록: {author_emails}")

        # GitHub GraphQL API로 유저의 모든 author 이름/이메일 조회
        try:
            repo_info = parse_repo_url(request.gitUrl)
            identities = get_user_author_identities_from_github(
                repo_info["owner"], repo_info["repo"], author_name, request.githubToken
            )
            if identities is None:
                raise AuthorMatchException("GitHub GraphQL API로 유저의 커밋 author 정보를 조회할 수 없습니다")
            # 기존 이메일 목록에 GitHub에서 발견된 이메일 추가
            for email in identities["emails"]:
                if email not in author_emails:
                    author_emails.append(email)
            logger.info(f"{log_prefix} GitHub GraphQL로 이름 {len(identities['names'])}개, 이메일 {len(identities['emails'])}개 발견")
        except Exception as e:
            raise AuthorMatchException(f"유저 커밋 author 매칭 실패: {e}") from e

        clone_start = time.time()
        logger.info(f"{log_prefix} Git 클론 중...")
        temp_dir = clone_repository(request.gitUrl, request.githubToken, settings.temp_dir)
        logger.info(f"{log_prefix} Git 클론 완료 ({time.time() - clone_start:.2f}초)")

        create_mailmap(temp_dir, author_name, author_emails)
        logger.info(f"{log_prefix} .mailmap 생성 완료")

        return author_name, author_emails, temp_dir

    async def _generate(
        self,
        request: Union[ReportGenerationReq, ReportGenerationSyncReq],
        temp_dir: str,
        author_name: str,
        author_emails: list,
        log_prefix: str,
    ) -> ReportOutcome:
        logger.info(f"{log_prefix} 리포트 생성 중 (engine={settings.report_engine})...")
        return await generate_report(
            dir_path=temp_dir,
            repo_url=request.gitUrl,
            author_name=author_name,
            author_emails=author_emails,
            available_techstacks=request.techstacks,
            log_prefix=log_prefix,
        )

    async def analyze_and_callback(self, request: ReportGenerationReq):
        temp_dir = None
        log_prefix = f"[detail:{request.detailReportId}, main:{request.mainReportId}]"

        logger.info(f"{log_prefix} 분석 시작 - {request.gitUrl}")

        try:
            author_name, author_emails, temp_dir = await asyncio.to_thread(
                self._clone_and_get_user_info, request, log_prefix
            )
            outcome = await self._generate(request, temp_dir, author_name, author_emails, log_prefix)
            logger.info(f"{log_prefix} AI 분석 완료, techstacks: {outcome.techstacks}")

            logger.info(f"{log_prefix} 콜백 전송 중...")
            await callback_service.send_success(
                callback_url=request.callbackUrl,
                detail_report_id=request.detailReportId,
                main_report_id=request.mainReportId,
                content=outcome.content,
                techstacks=outcome.techstacks
            )
            logger.info(f"{log_prefix} 콜백 전송 완료 (SUCCESS)")

            # 임베딩 생성 및 콜백 (실패해도 전체 프로세스는 계속 진행)
            await self._create_embedding_and_callback(request, outcome.content, log_prefix)

        except Exception as e:
            logger.error(f"{log_prefix} 오류 발생 - {str(e)}")
            await callback_service.send_failure(
                callback_url=request.callbackUrl,
                detail_report_id=request.detailReportId,
                main_report_id=request.mainReportId,
                error_message=str(e)
            )
            logger.info(f"{log_prefix} 콜백 전송 완료 (FAILED)")

        finally:
            if temp_dir:
                cleanup_directory(temp_dir)
                logger.info(f"{log_prefix} 임시 디렉토리 정리 완료")

    async def _create_embedding_and_callback(
        self,
        request: Union[ReportGenerationReq, ReportGenerationSyncReq],
        analysis_result: dict,
        log_prefix: str
    ):
        """리포트 임베딩 생성 및 콜백 전송"""
        try:
            logger.info(f"{log_prefix} 임베딩 생성 중...")
            text = extract_embedding_text(analysis_result.get("main", {}))

            if not text.strip():
                raise ValueError("임베딩할 텍스트가 비어있습니다")

            vector = await embedding_service.create_embedding(text)
            dimension = len(vector)
            logger.info(f"{log_prefix} 임베딩 생성 완료 (dimension: {dimension})")

            logger.info(f"{log_prefix} 임베딩 콜백 전송 중...")
            await callback_service.send_embedding_success(
                callback_url=request.embeddingCallbackUrl,
                detail_report_id=request.detailReportId,
                main_report_id=request.mainReportId,
                vector=vector,
                dimension=dimension
            )
            logger.info(f"{log_prefix} 임베딩 콜백 전송 완료 (SUCCESS)")

        except Exception as e:
            logger.error(f"{log_prefix} 임베딩 오류 발생 - {str(e)}")
            await callback_service.send_embedding_failure(
                callback_url=request.embeddingCallbackUrl,
                detail_report_id=request.detailReportId,
                main_report_id=request.mainReportId,
                error_message=str(e)
            )
            logger.info(f"{log_prefix} 임베딩 콜백 전송 완료 (FAILED)")

    async def analyze_sync(self, request: ReportGenerationSyncReq) -> dict:
        """동기식 분석 - 결과를 직접 반환"""
        temp_dir = None
        log_prefix = f"[detail:{request.detailReportId}, main:{request.mainReportId}]"
        start_time = time.time()

        logger.info(f"{log_prefix} 동기 분석 시작 - {request.gitUrl}")

        try:
            author_name, author_emails, temp_dir = await asyncio.to_thread(
                self._clone_and_get_user_info, request, log_prefix
            )
            outcome = await self._generate(request, temp_dir, author_name, author_emails, log_prefix)

            total_elapsed = time.time() - start_time
            logger.info(f"{log_prefix} 리포트 생성 완료 - 총 소요시간: {total_elapsed:.2f}초, techstacks: {outcome.techstacks}")

            # 임베딩 생성 및 콜백 (백그라운드에서 비동기 처리)
            asyncio.create_task(
                self._create_embedding_and_callback(request, outcome.content, log_prefix)
            )

            return {
                "status": "SUCCESS",
                "content": outcome.content,
                "errorMessage": None,
                "techstacks": outcome.techstacks
            }

        except Exception as e:
            total_elapsed = time.time() - start_time
            logger.error(f"{log_prefix} 오류 발생 ({total_elapsed:.2f}초) - {str(e)}")
            return {
                "status": "FAILED",
                "content": None,
                "errorMessage": str(e),
                "techstacks": []
            }

        finally:
            if temp_dir:
                cleanup_directory(temp_dir)
                logger.info(f"{log_prefix} 임시 디렉토리 정리 완료")


analyzer_service = AnalyzerService()
