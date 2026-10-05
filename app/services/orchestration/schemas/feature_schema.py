# Stage 1: Feature & Code Analysis Schema (v3 with AST, Metadata, Infra Guard)
# 엄격한 수량 상한선(Strict Bounds) + 인프라 및 메타데이터 지원:
# - implementedFeatures: 2~4개 카테고리
# - features per category: 1~3개
# - codeLocation per feature: 1~3개 (총 경로 15~25개 내외로 집중)
# - keyImplementations: 2~3개
# - codeInsights: 2~3개
# - infraAndDevOps: 인프라/설정/DevOps 전용 기여 항목
# - migrationMeta: 전사적 리팩토링/마이그레이션 메타데이터

FEATURE_SCHEMA = {
    "type": "object",
    "properties": {
        "techstacks": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Techstack enum values that the author directly worked with"
        },
        "migrationMeta": {
            "type": "object",
            "description": "전체 변경 규모 및 대규모 마이그레이션 메타데이터",
            "properties": {
                "totalFilesModified": {"type": "number"},
                "isLargeScale": {"type": "boolean"},
                "scopeDescription": {
                    "type": "string",
                    "description": "전역적인 구조 변경이나 마이그레이션이 있었는지, 핵심 15~25개 선별 맥락을 1~2문장으로 기술"
                }
            },
            "required": ["totalFilesModified", "isLargeScale", "scopeDescription"]
        },
        "infraAndDevOps": {
            "type": "object",
            "description": "인프라, CI/CD, 컨테이너, 빌드 설정 관련 기여 (해당 작업이 없으면 hasInfraWork=false)",
            "properties": {
                "hasInfraWork": {"type": "boolean"},
                "technologies": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "사용된 인프라/빌드 기술 (예: Docker, Terraform, GitHub Actions, Nginx, Vite, Webpack 등)"
                },
                "summary": {"type": "string", "description": "인프라 및 환경 설정 기여 핵심 요약 (없으면 빈 문자열)"},
                "keyFiles": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "기여한 인프라/설정 핵심 파일 목록 (최대 3개)"
                }
            },
            "required": ["hasInfraWork", "technologies", "summary", "keyFiles"]
        },
        "implementedFeatures": {
            "type": "array",
            "description": "구현 기능 카테고리 목록 (최대 3~4개 카테고리로 엄격히 제한)",
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "categoryNumber": {"type": "number"},
                    "features": {
                        "type": "array",
                        "description": "카테고리별 핵심 구현 기능 (최대 2~3개)",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "implementation": {
                                    "type": "array",
                                    "description": "구현 핵심 설명 (1~3개)",
                                    "items": {"type": "string"}
                                },
                                "codeLocation": {
                                    "type": "array",
                                    "description": "가장 핵심적인 실제 파일 경로 (최대 1~3개 파일로 엄격히 제한, 자잘한 헬퍼/아이콘 배제)",
                                    "items": {"type": "string"}
                                },
                                "details": {
                                    "type": "array",
                                    "description": "세부 구현 내용 (1~3개)",
                                    "items": {"type": "string"}
                                }
                            },
                            "required": ["name", "implementation", "codeLocation", "details"]
                        }
                    }
                },
                "required": ["category", "categoryNumber", "features"]
            }
        },
        "keyImplementations": {
            "type": "array",
            "description": "메인 리포트용 핵심 구현 (최대 2~3개)",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                },
                "required": ["title", "description", "tags"]
            }
        },
        "codeInsights": {
            "type": "array",
            "description": "코드 품질 및 아키텍처 인사이트 (최대 2~3개)",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "details": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                },
                "required": ["title", "details"]
            }
        },
        "myFeatures": {
            "type": "array",
            "description": "본인이 직접 구현한 주요 기능 목록 (최대 4~5개)",
            "items": {"type": "string"}
        },
        "otherFeatures": {
            "type": "array",
            "description": "다른 기여자가 구현한 주요 기능 목록 (최대 4~5개, 본인 기여와 혼동 방지용)",
            "items": {"type": "string"}
        }
    },
    "required": [
        "techstacks",
        "migrationMeta",
        "infraAndDevOps",
        "implementedFeatures",
        "keyImplementations",
        "codeInsights",
        "myFeatures",
        "otherFeatures"
    ]
}
