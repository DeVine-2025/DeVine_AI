<div align="center">

# DeVine AI Worker

**GitHub 레포지토리 분석 및 AI 리포트 생성 서비스**

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.124-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Gemini](https://img.shields.io/badge/Gemini_2.5_Flash-8E75B2?logo=googlegemini&logoColor=white)](https://ai.google.dev/)
[![OpenAI](https://img.shields.io/badge/OpenAI_Embeddings-412991?logo=openai&logoColor=white)](https://openai.com/)
[![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-2088FF?logo=githubactions&logoColor=white)](https://github.com/features/actions)

</div>

---

## 📌 Project Overview

**DeVine AI Worker**는 [DeVine BackEnd](https://github.com/DeVine-2025/DeVine_BackEnd)의 비동기 AI 워커 서비스입니다.

GitHub 레포지토리를 클론 · 분석하여 **개발자 기여도 리포트**를 자동 생성하고, 시맨틱 검색을 위한 **벡터 임베딩**을 제공합니다.

### 🎯 핵심 가치

| 가치 | 설명 |
|------|------|
| **AI 리포트 자동 생성** | Gemini 2.5 Flash 기반 구조화된 프로젝트 분석 리포트 |
| **동적 분석 스케일링** | 프로젝트 규모(커밋 수)에 따라 분석 깊이 자동 조절 |
| **벡터 임베딩** | OpenAI text-embedding-3-small (1536차원) 기반 유사도 검색 |
| **비동기 콜백 아키텍처** | 요청 즉시 202 응답 → 백그라운드 분석 → 콜백으로 결과 전달 |

---

## 🏗️ Architecture

```
DeVine_BackEnd (Spring Boot)
    │
    ├─ POST /api/v1/reports/generate ──→ DeVine_AI (FastAPI)
    │                                        │
    │    ← 202 ACCEPTED ─────────────────────┘
    │                                    [비동기 처리]
    │                                    Clone → Analyze → Gemini AI
    │                                        │
    ├─ POST /reports/callback ←─────────────┤  리포트 결과
    └─ POST /embeddings/callback ←──────────┘  임베딩 벡터
```

메인 백엔드가 분석 요청을 보내면 즉시 **202 응답**을 반환하고, 백그라운드에서 AI 분석을 수행한 뒤 **콜백으로 결과를 전달**합니다.

---

## ⚡ Key Features

### 1. 🤖 Gemini AI 리포트 생성
- 주요 구현사항, AI 평가, 기술적 의사결정 등 **구조화된 리포트** 생성
- Exponential backoff 기반 재시도 로직으로 API 호출 안정성 보장
- JSON 응답 파싱 실패 시 자동 복구 (`json-repair`)

### 2. 📊 동적 분석 스케일링
- 프로젝트 규모(커밋 수)에 따라 분석 깊이 자동 조절
- 파일 패턴 기반 **Tech Stack 자동 감지** (언어/프레임워크/DB/도구)

### 3. 🔢 벡터 임베딩
- OpenAI `text-embedding-3-small` 모델 (1536차원)
- 리포트 텍스트 및 프로젝트 설명 임베딩 생성
- Spring Boot 측 pgvector와 연동하여 유사도 검색 지원

### 4. 🔄 비동기 콜백 아키텍처
- 비동기 리포트 생성 (콜백 방식) + 동기 리포트 생성 모드 지원
- Git 클론 → 커밋 분석 → AI 리포트 생성 → 콜백 전송 파이프라인

---

## 🛠️ Tech Stack

| Category | Stack |
|----------|-------|
| **Runtime** | Python 3.12 |
| **Framework** | FastAPI, Uvicorn |
| **AI** | Google Gemini 2.5 Flash, OpenAI Embeddings |
| **Git** | GitPython |
| **Validation** | Pydantic v2 |
| **HTTP Client** | HTTPX |
| **Retry** | Tenacity (Exponential Backoff) |
| **Test** | pytest, pytest-asyncio |
| **Infra** | Docker, GitHub Actions, AWS EC2 |

---

## 📂 Project Structure

```
app/
├── configs/          # Settings, Logging 설정
├── controllers/      # 요청 핸들러 (report, embedding)
├── dtos/             # Request/Response 데이터 모델
├── errors/           # 커스텀 예외 (GitClone, Gemini, OpenAI 등)
├── middlewares/      # 에러 핸들러
├── prompts/          # Gemini AI 프롬프트 템플릿
├── routes/           # API 라우트 정의
├── services/         # 비즈니스 로직
│   ├── analyzer_service.py    # 분석 오케스트레이션
│   ├── git_service.py         # Git 클론/커밋 분석
│   ├── gemini_service.py      # Gemini AI 연동
│   ├── callback_service.py    # 백엔드 콜백
│   └── embedding_service.py   # OpenAI 임베딩
├── utils/            # 유틸리티 (tech_detector, file_reader 등)
└── main.py           # FastAPI 엔트리포인트
```

---

## 📖 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/reports/generate` | 비동기 리포트 생성 (콜백 방식) |
| `POST` | `/api/v1/reports/generate/sync` | 동기 리포트 생성 |
| `POST` | `/api/v1/embeddings/report` | 리포트 텍스트 임베딩 |
| `POST` | `/api/v1/embeddings/project` | 프로젝트 텍스트 임베딩 |
| `GET`  | `/health` | 헬스체크 |

---

## 🚀 Getting Started

### Prerequisites

- Python 3.12+
- Git

### Setup

```bash
# 1. 저장소 클론
git clone https://github.com/DeVine-2025/DeVine_AI.git
cd DeVine_AI

# 2. 가상환경 생성 및 활성화
python -m venv .venv
source .venv/bin/activate

# 3. 의존성 설치
pip install -r requirements.txt

# 4. 환경 변수 설정
cp .env.example .env
# .env 파일에 API 키 등 설정
```

### Run

```bash
# 개발 모드 (Hot Reload)
make dev

# 프로덕션 모드
make prod
```

### Docker

```bash
docker build -t devine-ai .
docker run -p 8000:8000 --env-file .env devine-ai
```

---

## ⚙️ Environment Variables

| Variable | Description |
|----------|-------------|
| `GEMINI_API_KEY` | Google Gemini API 키 |
| `OPENAI_API_KEY` | OpenAI API 키 |
| `EMBEDDING_MODEL` | 임베딩 모델 (기본: `text-embedding-3-small`) |
| `TEMP_DIR` | Git 클론 임시 디렉토리 (기본: `./temp`) |
| `LOG_LEVEL` | 로그 레벨 (기본: `INFO`) |
| `DEBUG` | 디버그 모드 (기본: `false`) |

---

## 🔄 CI/CD

```
main push → CI (flake8 Lint) → CD (Docker Build & Push → EC2 Deploy)
```

| 단계 | 설명 |
|------|------|
| **CI** | GitHub Actions → flake8 린트 검사 |
| **CD** | Docker Hub 이미지 푸시 → EC2 배포 (헬스체크 실패 시 자동 롤백) |

---

## 🌿 Git Convention

### 커밋 메시지

```
[TYPE] 변경 내용 요약
```

| 타입 | 설명 |
|------|------|
| `FEATURE` | 새로운 기능 추가 |
| `FIX` | 버그 수정 |
| `HOTFIX` | 긴급 버그 수정 |
| `REFACTOR` | 코드 리팩토링 |
| `CHORE` | 빌드, 설정 등 기타 변경 |
| `TEST` | 테스트 코드 |
| `DOCS` | 문서 추가/수정 |

### 브랜치 전략

```
main (프로덕션)
 └── dev (개발 통합)
      ├── feat/#10-report-api
      ├── fix/#25-gemini-parse
      └── ...
```

| 대상 | 머지 전략 |
|------|----------|
| 작업 브랜치 → `dev` | **Squash and Merge** |
| `dev` → `main` | **Merge Commit** |

---

<div align="center">

**DeVine AI** · Built with 🐍 by [DeVine Team](https://github.com/DeVine-2025)

</div>
