import os
import json
import subprocess
import asyncio
import logging
import time
from typing import Union
from dataclasses import dataclass
from app.dtos.request_dto import ReportGenerationReq, ReportGenerationSyncReq
from app.services.git_service import (
    clone_repository,
    cleanup_directory,
    create_mailmap,
    get_commit_count,
    get_commit_history,
    analyze_contributor_changes,
    get_all_contributors_summary,
    get_github_user_from_token,
    get_development_period,
    get_user_author_identities_from_github,
    parse_repo_url
)
from app.configs.settings import settings
from app.services.gemini_service import gemini_service
from app.services.callback_service import callback_service
from app.services.embedding_service import embedding_service
from app.utils.file_reader import get_code_files, count_lines, count_test_files
from app.utils.tech_detector import detect_tech_stack
from app.utils.tree_builder import build_project_tree
from app.utils.text_processor import extract_embedding_text
from app.prompts.combined_report_prompt import get_combined_report_prompt
from app.errors.exceptions import AuthorMatchException

logger = logging.getLogger(__name__)


@dataclass
class AnalysisLimits:
    max_commit_messages: int
    max_files: int
    max_commits_per_file: int
    max_added_lines: int
    max_deleted_lines: int


def calculate_dynamic_limits(user_commits: int, files_modified: int) -> AnalysisLimits:
    if user_commits < 50 and files_modified < 30:
        return AnalysisLimits(
            max_commit_messages=999,
            max_files=999,
            max_commits_per_file=999,
            max_added_lines=999,
            max_deleted_lines=999
        )

    if user_commits < 200 and files_modified < 100:
        return AnalysisLimits(
            max_commit_messages=100,
            max_files=80,
            max_commits_per_file=10,
            max_added_lines=100,
            max_deleted_lines=50
        )

    if user_commits < 500:
        return AnalysisLimits(
            max_commit_messages=80,
            max_files=60,
            max_commits_per_file=5,
            max_added_lines=50,
            max_deleted_lines=30
        )

    return AnalysisLimits(
        max_commit_messages=50,
        max_files=40,
        max_commits_per_file=3,
        max_added_lines=30,
        max_deleted_lines=20
    )


class AnalyzerService:
    def _clone_and_get_user_info(self, request: ReportGenerationReq) -> tuple:
        author_name, author_email = get_github_user_from_token(request.githubToken)
        author_emails = request.authorEmails if request.authorEmails else [author_email]
        log_prefix = f"[detail:{request.detailReportId}, main:{request.mainReportId}]"
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

        logger.info(f"{log_prefix} Git 클론 중...")
        temp_dir = clone_repository(request.gitUrl, request.githubToken, settings.temp_dir)
        logger.info(f"{log_prefix} Git 클론 완료")

        create_mailmap(temp_dir, author_name, author_emails)
        logger.info(f"{log_prefix} .mailmap 생성 완료")

        return author_name, author_email, author_emails, temp_dir

    async def analyze_and_callback(self, request: ReportGenerationReq):
        temp_dir = None
        log_prefix = f"[detail:{request.detailReportId}, main:{request.mainReportId}]"

        logger.info(f"{log_prefix} 분석 시작 - {request.gitUrl}")

        try:
            author_name, author_email, author_emails, temp_dir = await asyncio.to_thread(
                self._clone_and_get_user_info, request
            )

            logger.info(f"{log_prefix} 기여자 분석 중...")
            analysis_result = await self._analyze_contributor(
                temp_dir, request.gitUrl, author_name, author_email, request.techstacks, author_emails
            )
            logger.info(f"{log_prefix} AI 분석 완료")

            # techstacks 추출 (AI 응답에서)
            techstacks = analysis_result.pop("techstacks", []) if isinstance(analysis_result, dict) else []
            logger.info(f"{log_prefix} AI 응답 techstacks: {techstacks}")

            logger.info(f"{log_prefix} 콜백 전송 중...")
            await callback_service.send_success(
                callback_url=request.callbackUrl,
                detail_report_id=request.detailReportId,
                main_report_id=request.mainReportId,
                content=analysis_result,
                techstacks=techstacks
            )
            logger.info(f"{log_prefix} 콜백 전송 완료 (SUCCESS)")

            # 임베딩 생성 및 콜백 (실패해도 전체 프로세스는 계속 진행)
            await self._create_embedding_and_callback(request, analysis_result, log_prefix)

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

    def _analyze_contributor_sync(self, dir_path: str, repo_url: str, author_name: str, author_email: str, available_techstacks: list = None, author_emails: list = None) -> str:
        tech_stack = detect_tech_stack(dir_path)
        tech_stack_str = json.dumps(tech_stack, ensure_ascii=False, indent=2)

        tree_structure = build_project_tree(dir_path)

        code_files = get_code_files(dir_path)
        total_files = len(code_files)
        total_lines = sum(count_lines(os.path.join(dir_path, f)) for f in code_files)

        total_commits = get_commit_count(dir_path)

        preliminary_commits = get_commit_history(dir_path, author_name, author_email, author_emails)
        preliminary_files_count = len(set(
            f["path"] for c in preliminary_commits[:50]
            for f in self._get_commit_files_quick(dir_path, c["hash"])
        )) if preliminary_commits else 0

        limits = calculate_dynamic_limits(len(preliminary_commits), preliminary_files_count)
        logger.info(f"동적 제한값: 커밋 {len(preliminary_commits)}개, 파일 약 {preliminary_files_count}개")

        contributor_changes = analyze_contributor_changes(
            dir_path, author_name, author_email,
            author_emails=author_emails,
            max_added_lines=limits.max_added_lines,
            max_deleted_lines=limits.max_deleted_lines
        )

        user_commits = contributor_changes["stats"]["totalCommits"]
        contribution_ratio = round(
            (user_commits / total_commits * 100) if total_commits > 0 else 0, 1
        )

        commit_messages = "\n".join(
            contributor_changes["commitMessages"][:limits.max_commit_messages]
        )

        file_changes = self._format_file_changes(
            contributor_changes["files"],
            max_files=limits.max_files,
            max_commits_per_file=limits.max_commits_per_file
        )

        other_contributors = get_all_contributors_summary(dir_path, exclude_author=author_name, exclude_emails=author_emails)
        other_contributors_str = "\n".join([
            f"- {name}: {data['commits']}커밋"
            for name, data in other_contributors.items()
        ][:10])

        development_period = get_development_period(dir_path)
        test_code_count = count_test_files(dir_path)

        prompt = get_combined_report_prompt(
            repo_url=repo_url,
            author_name=author_name,
            total_commits=total_commits,
            user_commits=user_commits,
            contribution_ratio=contribution_ratio,
            tech_stack=tech_stack_str,
            total_files=total_files,
            total_lines=total_lines,
            tree_structure=tree_structure,
            lines_added=contributor_changes["stats"]["totalAdded"],
            lines_deleted=contributor_changes["stats"]["totalDeleted"],
            files_modified=contributor_changes["stats"]["filesModified"],
            commit_messages=commit_messages,
            file_changes=file_changes,
            other_contributors=other_contributors_str,
            development_period=development_period,
            test_code_count=test_code_count,
            available_techstacks=available_techstacks
        )

        return prompt

    async def _analyze_contributor(self, dir_path: str, repo_url: str, author_name: str, author_email: str, available_techstacks: list = None, author_emails: list = None) -> dict:
        prompt = await asyncio.to_thread(
            self._analyze_contributor_sync, dir_path, repo_url, author_name, author_email, available_techstacks, author_emails
        )
        result = await gemini_service.analyze_code(prompt)
        return result

    async def analyze_sync(self, request: ReportGenerationSyncReq) -> dict:
        """동기식 분석 - 결과를 직접 반환"""
        temp_dir = None
        log_prefix = f"[detail:{request.detailReportId}, main:{request.mainReportId}]"
        start_time = time.time()

        logger.info(f"{log_prefix} 동기 분석 시작 - {request.gitUrl}")

        try:
            author_name, author_email = get_github_user_from_token(request.githubToken)
            author_emails = request.authorEmails if request.authorEmails else [author_email]
            logger.info(f"{log_prefix} 분석 대상: {author_name} ({author_email}), 이메일 목록: {author_emails}")

            # GitHub GraphQL API로 유저의 모든 author 이름/이메일 조회
            try:
                repo_info = parse_repo_url(request.gitUrl)
                identities = get_user_author_identities_from_github(
                    repo_info["owner"], repo_info["repo"], author_name, request.githubToken
                )
                if identities is None:
                    raise AuthorMatchException("GitHub GraphQL API로 유저의 커밋 author 정보를 조회할 수 없습니다")
                for email in identities["emails"]:
                    if email not in author_emails:
                        author_emails.append(email)
                logger.info(f"{log_prefix} GitHub GraphQL로 이름 {len(identities['names'])}개, 이메일 {len(identities['emails'])}개 발견")
            except Exception as e:
                raise AuthorMatchException(f"유저 커밋 author 매칭 실패: {e}") from e

            clone_start = time.time()
            logger.info(f"{log_prefix} Git 클론 중...")
            temp_dir = await asyncio.to_thread(
                clone_repository, request.gitUrl, request.githubToken, settings.temp_dir
            )
            clone_elapsed = time.time() - clone_start
            logger.info(f"{log_prefix} Git 클론 완료 ({clone_elapsed:.2f}초)")

            create_mailmap(temp_dir, author_name, author_emails)
            logger.info(f"{log_prefix} .mailmap 생성 완료")

            analysis_start = time.time()
            logger.info(f"{log_prefix} 기여자 분석 중...")
            analysis_result = await self._analyze_contributor(
                temp_dir, request.gitUrl, author_name, author_email, request.techstacks, author_emails
            )
            analysis_elapsed = time.time() - analysis_start
            logger.info(f"{log_prefix} AI 분석 완료 ({analysis_elapsed:.2f}초)")

            total_elapsed = time.time() - start_time
            logger.info(f"{log_prefix} 리포트 생성 완료 - 총 소요시간: {total_elapsed:.2f}초")

            # 임베딩 생성 및 콜백 (백그라운드에서 비동기 처리)
            asyncio.create_task(
                self._create_embedding_and_callback(request, analysis_result, log_prefix)
            )

            # techstacks 추출 (AI 응답에서)
            techstacks = analysis_result.pop("techstacks", []) if isinstance(analysis_result, dict) else []
            logger.info(f"{log_prefix} AI 응답 techstacks: {techstacks}")

            return {
                "status": "SUCCESS",
                "content": analysis_result,
                "errorMessage": None,
                "techstacks": techstacks
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

    def _get_commit_files_quick(self, dir_path: str, commit_hash: str) -> list:
        try:
            result = subprocess.run(
                ["git", "show", "--name-only", "--format=", commit_hash],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                cwd=dir_path
            )
            if result.returncode == 0:
                return [{"path": f} for f in result.stdout.strip().split("\n") if f]
            return []
        except Exception:
            return []

    def _format_file_changes(self, files: dict, max_files: int = 999, max_commits_per_file: int = 999) -> str:
        parts = []

        sorted_files = sorted(
            files.items(),
            key=lambda x: x[1]["commits"],
            reverse=True
        )[:max_files]

        for path, data in sorted_files:
            part = f"\n=== {path} (커밋 {data['commits']}회) ===\n"

            for change in data["changes"][:max_commits_per_file]:
                part += f"[{change['date']}] {change['message']}\n"

                if change["added"]:
                    added_preview = "\n".join(change["added"])
                    part += f"+추가:\n{added_preview}\n"

                if change["deleted"]:
                    deleted_preview = "\n".join(change["deleted"])
                    part += f"-삭제:\n{deleted_preview}\n"

            parts.append(part)

        return "\n".join(parts)


analyzer_service = AnalyzerService()
