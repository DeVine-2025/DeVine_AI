# DeVine AI Worker

**DeVine_BackEnd**의 비동기 AI 워커 서비스입니다. GitHub 레포지토리를 분석하여 개발자 기여도 리포트를 생성하고, 시맨틱 검색을 위한 벡터 임베딩을 제공합니다.

## Architecture

```
DeVine_BackEnd (Spring Boot)
    │
    ├─ POST /api/v1/reports/generate ──→ DeVine_AI (FastAPI)
    │                                        │
    │   ← 202 ACCEPTED ─────────────────────┘
    │                                    [비동기 처리]
    │                                    Clone → Analyze → Gemini AI
    │                                        │
    ├─ POST /reports/callback ←─────────────┤  리포트 결과
    └─ POST /embeddings/callback ←──────────┘  임베딩 벡터
```

메인 백엔드가 분석 요청을 보내면 즉시 202 응답을 반환하고, 백그라운드에서 AI 분석을 수행한 뒤 콜백으로 결과를 전달합니다.

## Tech Stack

| Category | Stack |
|----------|-------|
| Runtime | Python 3.12 |
| Framework | FastAPI, Uvicorn |
| AI | Google Gemini 2.5 Flash, OpenAI Embeddings |
| Git | GitPython |
| Infra | Docker, GitHub Actions, AWS EC2 |

## Project Structure

```
app/
├── configs/        # Settings, Logging 설정
├── controllers/    # 요청 핸들러 (report, embedding)
├── dtos/           # Request/Response 데이터 모델
├── errors/         # 커스텀 예외 (GitClone, Gemini, OpenAI 등)
├── middlewares/     # 에러 핸들러
├── prompts/        # Gemini AI 프롬프트 템플릿
├── routes/         # API 라우트 정의
├── services/       # 비즈니스 로직
│   ├── analyzer_service.py    # 분석 오케스트레이션
│   ├── git_service.py         # Git 클론/커밋 분석
│   ├── gemini_service.py      # Gemini AI 연동
│   ├── callback_service.py    # 백엔드 콜백
│   └── embedding_service.py   # OpenAI 임베딩
├── utils/          # 유틸리티 (tech_detector, file_reader 등)
└── main.py         # FastAPI 엔트리포인트
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/reports/generate` | 비동기 리포트 생성 (콜백 방식) |
| `POST` | `/api/v1/reports/generate/sync` | 동기 리포트 생성 |
| `POST` | `/api/v1/embeddings/report` | 리포트 텍스트 임베딩 |
| `POST` | `/api/v1/embeddings/project` | 프로젝트 텍스트 임베딩 |
| `GET`  | `/health` | 헬스체크 |

## Key Features

- **동적 분석 스케일링** — 프로젝트 규모(커밋 수)에 따라 분석 깊이 자동 조절
- **Tech Stack 자동 감지** — 파일 패턴 기반 언어/프레임워크/DB/도구 분류
- **Gemini 리포트 생성** — 주요 구현사항, AI 평가, 기술적 의사결정 등 구조화된 리포트
- **임베딩 벡터 생성** — OpenAI text-embedding-3-small (1536차원)
- **재시도 로직** — Exponential backoff 기반 API 호출 안정성 보장

## Getting Started

### Prerequisites

- Python 3.12+
- Git

### Setup

```bash
# 의존성 설치
pip install -r requirements.txt

# 환경 변수 설정
cp .env.example .env
# .env 파일에 GEMINI_API_KEY, OPENAI_API_KEY 등 설정
```

### Run

```bash
# 개발 모드
make dev

# 프로덕션 모드
make prod
```

### Docker

```bash
docker build -t devine-ai .
docker run -p 8000:8000 --env-file .env devine-ai
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `GEMINI_API_KEY` | Google Gemini API 키 |
| `OPENAI_API_KEY` | OpenAI API 키 |
| `EMBEDDING_MODEL` | 임베딩 모델 (기본: text-embedding-3-small) |
| `TEMP_DIR` | Git 클론 임시 디렉토리 (기본: ./temp) |
| `LOG_LEVEL` | 로그 레벨 (기본: INFO) |
| `DEBUG` | 디버그 모드 (기본: false) |

## CI/CD

- **CI**: GitHub Actions → flake8 린트 검사
- **CD**: Docker Hub 푸시 → EC2 배포 (헬스체크 실패 시 자동 롤백)
