"""
프로젝트 임베딩 API 테스트

실행 방법:
    pytest test/test_embed_project.py -v
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.controllers.embedding_controller import MAX_INPUT_LENGTH


# Mock 벡터 생성 (1536차원)
MOCK_VECTOR = [0.1] * 1536


@pytest.fixture
def client():
    """테스트 클라이언트"""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def mock_embedding():
    """embedding_service.create_embedding Mock"""
    with patch(
        "app.controllers.embedding_controller.embedding_service.create_embedding",
        new_callable=AsyncMock,
        return_value=MOCK_VECTOR,
    ) as mock:
        yield mock


class TestEmbedProject:
    """POST /api/v1/embeddings/project 엔드포인트 테스트"""

    def test_embed_project_success(self, client, mock_embedding):
        """정상적인 텍스트로 임베딩 생성"""
        response = client.post(
            "/api/v1/embeddings/project",
            json={"text": "[도메인: FINTECH] 금융 결제 시스템 개발 프로젝트입니다."},
        )

        assert response.status_code == 200
        data = response.json()
        assert "vector" in data
        assert "dimension" in data
        assert data["dimension"] == 1536
        assert len(data["vector"]) == 1536
        assert all(isinstance(v, float) for v in data["vector"])
        mock_embedding.assert_called_once()

    def test_embed_project_empty_text(self, client, mock_embedding):
        """빈 텍스트 에러 처리"""
        response = client.post(
            "/api/v1/embeddings/project",
            json={"text": ""},
        )

        assert response.status_code == 400
        data = response.json()
        assert data["code"] == "EMPTY_TEXT"
        mock_embedding.assert_not_called()

    def test_embed_project_whitespace_only(self, client, mock_embedding):
        """공백만 있는 텍스트 에러 처리"""
        response = client.post(
            "/api/v1/embeddings/project",
            json={"text": "   "},
        )

        assert response.status_code == 400
        data = response.json()
        assert data["code"] == "EMPTY_TEXT"
        mock_embedding.assert_not_called()

    def test_embed_project_missing_text_field(self, client, mock_embedding):
        """text 필드 누락 에러"""
        response = client.post(
            "/api/v1/embeddings/project",
            json={},
        )

        assert response.status_code == 422  # Pydantic validation error
        mock_embedding.assert_not_called()

    def test_embed_project_text_too_long(self, client, mock_embedding):
        """텍스트 길이 초과 에러 처리"""
        long_text = "a" * (MAX_INPUT_LENGTH + 1)
        response = client.post(
            "/api/v1/embeddings/project",
            json={"text": long_text},
        )

        assert response.status_code == 400
        data = response.json()
        assert data["code"] == "TEXT_TOO_LONG"
        mock_embedding.assert_not_called()


class TestEmbedReport:
    """POST /api/v1/embeddings/report 엔드포인트 테스트"""

    def test_embed_report_success(self, client, mock_embedding):
        """리포트 임베딩 정상 동작 확인"""
        mock_report = {
            "overview": {
                "summary": "테스트 프로젝트 요약",
                "mainTech": "Python",
            },
            "projectInfo": {
                "techStack": ["Python", "FastAPI"],
            },
            "keyImplementations": [
                {"title": "기능 구현"},
            ],
        }

        response = client.post(
            "/api/v1/embeddings/report",
            json={"report": mock_report},
        )

        assert response.status_code == 200
        data = response.json()
        assert "vector" in data
        assert data["dimension"] == 1536
        mock_embedding.assert_called_once()

    def test_embed_report_text_too_long(self, client, mock_embedding):
        """리포트 텍스트 길이 초과 에러 처리"""
        long_summary = "a" * (MAX_INPUT_LENGTH + 1)
        mock_report = {
            "overview": {
                "summary": long_summary,
            },
        }

        response = client.post(
            "/api/v1/embeddings/report",
            json={"report": mock_report},
        )

        assert response.status_code == 400
        data = response.json()
        assert data["code"] == "TEXT_TOO_LONG"
        mock_embedding.assert_not_called()
