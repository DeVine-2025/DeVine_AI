"""
Analyzer 서비스 임베딩 통합 테스트

이 테스트는 리포트 분석 후 임베딩 생성 및 콜백 전송이 정상적으로 이루어지는지 검증합니다.

실행 방법:
    pytest test/test_analyzer_embedding.py -v -s
"""

import contextlib
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.analyzer_service import analyzer_service
from app.dtos.request_dto import ReportGenerationReq


# Mock 데이터
MOCK_ANALYSIS_RESULT = {
    "main": {
        "overview": {
            "summary": "테스트 프로젝트 요약입니다.",
            "mainTech": "Python, FastAPI"
        },
        "projectInfo": {
            "techStack": ["Python", "FastAPI", "PostgreSQL"]
        },
        "keyImplementations": [
            {"title": "사용자 인증 시스템 구현"},
            {"title": "RESTful API 설계 및 개발"}
        ]
    }
}

MOCK_EMBEDDING_VECTOR = [0.1] * 1536


@pytest.fixture
def mock_request():
    """테스트용 ReportGenerationReq 객체"""
    return ReportGenerationReq(
        detailReportId=1,
        mainReportId=100,
        gitUrl="https://github.com/test/repo.git",
        callbackUrl="http://backend.test/api/v1/reports/callback",
        embeddingCallbackUrl="http://backend.test/api/v1/embeddings/callback",
        githubToken="test_token_12345"
    )


@pytest.fixture
def mock_services():
    """모든 외부 서비스 Mock"""
    prefix = "app.services.analyzer_service"
    with contextlib.ExitStack() as stack:
        mock_gh = stack.enter_context(patch(f"{prefix}.get_github_user_from_token"))
        mock_clone = stack.enter_context(patch(f"{prefix}.clone_repository"))
        mock_cleanup = stack.enter_context(patch(f"{prefix}.cleanup_directory"))
        mock_mailmap = stack.enter_context(patch(f"{prefix}.create_mailmap"))
        mock_tree = stack.enter_context(patch(f"{prefix}.build_project_tree"))
        mock_tech = stack.enter_context(patch(f"{prefix}.detect_tech_stack"))
        mock_files = stack.enter_context(patch(f"{prefix}.get_code_files"))
        mock_lines = stack.enter_context(patch(f"{prefix}.count_lines"))
        mock_test_files = stack.enter_context(patch(f"{prefix}.count_test_files"))
        mock_commit_count = stack.enter_context(patch(f"{prefix}.get_commit_count"))
        mock_commit_history = stack.enter_context(patch(f"{prefix}.get_commit_history"))
        mock_contributor = stack.enter_context(patch(f"{prefix}.analyze_contributor_changes"))
        mock_all_contributors = stack.enter_context(patch(f"{prefix}.get_all_contributors_summary"))
        mock_dev_period = stack.enter_context(patch(f"{prefix}.get_development_period"))
        mock_identities = stack.enter_context(patch(f"{prefix}.get_user_author_identities_from_github"))
        mock_parse_url = stack.enter_context(patch(f"{prefix}.parse_repo_url"))
        mock_gemini = stack.enter_context(patch(f"{prefix}.gemini_service.analyze_code", new_callable=AsyncMock))
        mock_callback_success = stack.enter_context(patch(f"{prefix}.callback_service.send_success", new_callable=AsyncMock))
        mock_callback_failure = stack.enter_context(patch(f"{prefix}.callback_service.send_failure", new_callable=AsyncMock))
        mock_embedding = stack.enter_context(patch(f"{prefix}.embedding_service.create_embedding", new_callable=AsyncMock))
        mock_embedding_callback = stack.enter_context(patch(f"{prefix}.callback_service.send_embedding_success", new_callable=AsyncMock))

        # Mock 설정
        mock_gh.return_value = ("test_user", "test@example.com")
        mock_clone.return_value = "/tmp/test_repo"
        mock_parse_url.return_value = {"owner": "test", "repo": "repo"}
        mock_identities.return_value = {"names": {"test_user"}, "emails": {"test@example.com"}}
        mock_tree.return_value = "test_tree_structure"
        mock_tech.return_value = {"JavaScript": ["React", "Node.js"]}
        mock_files.return_value = ["file1.js", "file2.js"]
        mock_lines.return_value = 100
        mock_test_files.return_value = 5
        mock_commit_count.return_value = 100
        mock_commit_history.return_value = [{"hash": "abc123", "message": "test commit"}]
        mock_contributor.return_value = {
            "stats": {"totalCommits": 50, "totalAdded": 1000, "totalDeleted": 200, "filesModified": 10},
            "files": {},
            "commitMessages": ["test commit 1", "test commit 2"]
        }
        mock_all_contributors.return_value = {}
        mock_dev_period.return_value = "2024-01-01 ~ 2024-02-09"
        mock_gemini.return_value = MOCK_ANALYSIS_RESULT
        mock_embedding.return_value = MOCK_EMBEDDING_VECTOR

        yield {
            "github": mock_gh,
            "clone": mock_clone,
            "cleanup": mock_cleanup,
            "gemini": mock_gemini,
            "callback_success": mock_callback_success,
            "callback_failure": mock_callback_failure,
            "embedding": mock_embedding,
            "embedding_callback": mock_embedding_callback
        }


class TestAnalyzerEmbedding:
    """Analyzer 임베딩 통합 테스트"""

    @pytest.mark.asyncio
    async def test_analyze_and_callback_with_embedding_success(self, mock_request, mock_services):
        """리포트 분석 성공 후 임베딩 생성 및 콜백 전송 테스트"""

        # 실행
        await analyzer_service.analyze_and_callback(mock_request)

        # 검증 1: Git 클론 및 사용자 정보 조회
        mock_services["github"].assert_called_once_with(mock_request.githubToken)
        mock_services["clone"].assert_called_once()

        # 검증 2: AI 분석 실행
        mock_services["gemini"].assert_called_once()

        # 검증 3: 리포트 콜백 전송
        mock_services["callback_success"].assert_called_once_with(
            callback_url=mock_request.callbackUrl,
            detail_report_id=mock_request.detailReportId,
            main_report_id=mock_request.mainReportId,
            content=MOCK_ANALYSIS_RESULT,
            techstacks=[]
        )

        # 검증 4: 임베딩 생성
        mock_services["embedding"].assert_called_once()

        # 검증 5: 임베딩 콜백 전송
        mock_services["embedding_callback"].assert_called_once_with(
            callback_url=mock_request.embeddingCallbackUrl,
            detail_report_id=mock_request.detailReportId,
            main_report_id=mock_request.mainReportId,
            vector=MOCK_EMBEDDING_VECTOR,
            dimension=1536
        )

        # 검증 6: 정리 작업
        mock_services["cleanup"].assert_called_once_with("/tmp/test_repo")

    @pytest.mark.asyncio
    async def test_embedding_failure_does_not_affect_main_process(self, mock_request, mock_services):
        """임베딩 실패 시에도 전체 프로세스는 성공해야 함"""

        # 임베딩 생성을 실패하도록 설정
        mock_services["embedding"].side_effect = Exception("OpenAI API 오류")

        # 임베딩 실패 콜백 Mock 추가
        with patch("app.services.analyzer_service.callback_service.send_embedding_failure", new_callable=AsyncMock) as mock_embedding_failure:
            # 실행
            await analyzer_service.analyze_and_callback(mock_request)

            # 검증 1: 리포트 콜백은 여전히 성공
            mock_services["callback_success"].assert_called_once()

            # 검증 2: 임베딩 실패 콜백 전송
            mock_embedding_failure.assert_called_once()

            # 검증 3: 정리 작업 완료
            mock_services["cleanup"].assert_called_once()

    @pytest.mark.asyncio
    async def test_main_process_failure_prevents_embedding(self, mock_request, mock_services):
        """메인 분석 실패 시 임베딩은 실행되지 않아야 함"""

        # AI 분석을 실패하도록 설정
        mock_services["gemini"].side_effect = Exception("Gemini API 오류")

        # 실행
        await analyzer_service.analyze_and_callback(mock_request)

        # 검증 1: 실패 콜백 전송
        mock_services["callback_failure"].assert_called_once_with(
            callback_url=mock_request.callbackUrl,
            detail_report_id=mock_request.detailReportId,
            main_report_id=mock_request.mainReportId,
            error_message="Gemini API 오류"
        )

        # 검증 2: 임베딩은 호출되지 않음
        mock_services["embedding"].assert_not_called()
        mock_services["embedding_callback"].assert_not_called()

        # 검증 3: 정리 작업은 완료
        mock_services["cleanup"].assert_called_once()


class TestCreateEmbeddingAndCallback:
    """_create_embedding_and_callback 메서드 단위 테스트"""

    @pytest.mark.asyncio
    async def test_create_embedding_success(self, mock_request):
        """임베딩 생성 및 콜백 성공 테스트"""

        with patch("app.services.analyzer_service.embedding_service.create_embedding", new_callable=AsyncMock) as mock_embedding, \
             patch("app.services.analyzer_service.callback_service.send_embedding_success", new_callable=AsyncMock) as mock_callback:

            mock_embedding.return_value = MOCK_EMBEDDING_VECTOR

            # 실행
            await analyzer_service._create_embedding_and_callback(
                request=mock_request,
                analysis_result=MOCK_ANALYSIS_RESULT,
                log_prefix="[TEST]"
            )

            # 검증
            mock_embedding.assert_called_once()
            mock_callback.assert_called_once_with(
                callback_url=mock_request.embeddingCallbackUrl,
                detail_report_id=mock_request.detailReportId,
                main_report_id=mock_request.mainReportId,
                vector=MOCK_EMBEDDING_VECTOR,
                dimension=1536
            )

    @pytest.mark.asyncio
    async def test_empty_text_error(self, mock_request):
        """빈 텍스트 에러 처리 테스트"""

        empty_result = {"main": {}}

        with patch("app.services.analyzer_service.embedding_service.create_embedding", new_callable=AsyncMock) as mock_embedding, \
             patch("app.services.analyzer_service.callback_service.send_embedding_failure", new_callable=AsyncMock) as mock_failure:

            # 실행
            await analyzer_service._create_embedding_and_callback(
                request=mock_request,
                analysis_result=empty_result,
                log_prefix="[TEST]"
            )

            # 검증: 임베딩은 호출되지 않고 실패 콜백만 전송
            mock_embedding.assert_not_called()
            mock_failure.assert_called_once()
            assert "임베딩할 텍스트가 비어있습니다" in str(mock_failure.call_args)

    @pytest.mark.asyncio
    async def test_embedding_api_error(self, mock_request):
        """임베딩 API 오류 처리 테스트"""

        with patch("app.services.analyzer_service.embedding_service.create_embedding", new_callable=AsyncMock) as mock_embedding, \
             patch("app.services.analyzer_service.callback_service.send_embedding_failure", new_callable=AsyncMock) as mock_failure:

            mock_embedding.side_effect = Exception("OpenAI API Rate Limit")

            # 실행
            await analyzer_service._create_embedding_and_callback(
                request=mock_request,
                analysis_result=MOCK_ANALYSIS_RESULT,
                log_prefix="[TEST]"
            )

            # 검증
            mock_embedding.assert_called_once()
            mock_failure.assert_called_once()
            assert "OpenAI API Rate Limit" in str(mock_failure.call_args)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
