"""
핵심 로직 테스트 스크립트

실행 방법:
    python -m tests.test_core

환경 변수:
    OPENAI_API_KEY: OpenAI API 키 (.env 파일 또는 환경 변수)
"""

import asyncio
import sys
from pathlib import Path

# 프로젝트 루트를 path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from app.utils.text_processor import extract_embedding_text
from app.services.embedding_service import EmbeddingService
from app.core.config import get_settings

# 테스트용 Mock 리포트 데이터
MOCK_REPORT = {
    "overview": {
        "summary": "이 프로젝트는 다양한 외부 음악 API(Last.fm, iTunes, Spotify, Billboard)와 연동하여 음악 정보를 제공하고, 사용자별 음악 보관함 및 AI 기반 추천 기능을 포함하는 백엔드 시스템입니다.",
        "mainTech": "JavaScript 기반 Express.js 프레임워크를 활용한 백엔드 API 서버 개발",
        "capabilities": [
            "JWT 기반 사용자 인증 및 권한 관리 시스템",
            "다수의 외부 음악 API 연동",
        ],
        "scale": "약 8,625줄 코드 작성",
    },
    "projectInfo": {
        "projectName": "UMC Archive Backend",
        "techStack": [
            "JavaScript",
            "Express.js",
            "Prisma",
            "OpenAI API",
            "AWS SDK (S3)",
        ],
        "scale": "8,625줄",
    },
    "keyImplementations": [
        {
            "title": "외부 음악 서비스 API 통합 및 데이터 관리",
            "description": "Last.fm, iTunes, Spotify, Billboard와 같은 여러 외부 음악 API들을 통합...",
        },
        {
            "title": "사용자 인증 및 권한 부여 시스템",
            "description": "JWT를 이용한 사용자 로그인, 회원가입...",
        },
        {
            "title": "AI 기반 음악 추천 및 사용자 맞춤형 서비스",
            "description": "OpenAI GPT API를 활용하여 사용자 히스토리 기반 추천...",
        },
    ],
}


def test_text_processor():
    """텍스트 전처리 테스트"""
    print("\n[1] 텍스트 전처리 테스트")
    print("-" * 50)

    text = extract_embedding_text(MOCK_REPORT)

    print(f"추출된 텍스트 ({len(text)}자):\n")
    print(text)
    print("-" * 50)

    assert len(text) > 0, "텍스트가 비어있습니다"
    assert "Express.js" in text, "mainTech가 포함되어야 합니다"
    assert "JavaScript" in text, "techStack이 포함되어야 합니다"
    assert "외부 음악 서비스 API 통합" in text, "keyImplementations 제목이 포함되어야 합니다"

    print("텍스트 전처리 테스트 통과")
    return text


async def test_embedding_service(text: str):
    """임베딩 서비스 테스트"""
    print("\n[2] 임베딩 서비스 테스트")
    print("-" * 50)

    settings = get_settings()
    print(f"모델: {settings.EMBEDDING_MODEL}")
    print(f"예상 차원: {settings.EMBEDDING_DIMENSION}")

    service = EmbeddingService()
    vector = await service.create_embedding(text)

    print(f"\n생성된 벡터 차원: {len(vector)}")
    print(f"벡터 샘플 (처음 5개): {vector[:5]}")
    print("-" * 50)

    assert len(vector) == settings.EMBEDDING_DIMENSION, f"차원이 {settings.EMBEDDING_DIMENSION}이어야 합니다"
    assert all(isinstance(v, float) for v in vector), "모든 값이 float이어야 합니다"

    print("임베딩 서비스 테스트 통과")
    return vector


async def main():
    print("=" * 50)
    print("DeVine AI 핵심 로직 테스트")
    print("=" * 50)

    try:
        # 1. 텍스트 전처리 테스트
        text = test_text_processor()

        # 2. 임베딩 서비스 테스트
        vector = await test_embedding_service(text)

        print("\n" + "=" * 50)
        print("모든 테스트 통과!")
        print("=" * 50)

    except AssertionError as e:
        print(f"\n테스트 실패: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n오류 발생: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
