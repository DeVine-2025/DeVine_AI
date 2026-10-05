# Stage 1: Feature & Code Analysis Schema
# 엄격한 수량 상한선(Strict Bounds) 적용:
# - implementedFeatures: 2~4개 카테고리
# - features per category: 1~3개
# - codeLocation per feature: 1~3개 (총 경로 15~25개 내외로 집중)
# - keyImplementations: 2~3개
# - codeInsights: 2~3개

FEATURE_SCHEMA = {
    "type": "object",
    "properties": {
        "techstacks": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Techstack enum values that the author directly worked with"
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
                    "capabilities": {
                        "type": "array",
                        "description": "관련 역량 키워드 (2~3개)",
                        "items": {"type": "string"}
                    }
                },
                "required": ["title", "description", "capabilities"]
            }
        },
        "projectSummary": {
            "type": "object",
            "properties": {
                "implemented": {
                    "type": "array",
                    "description": "본인 구현 주요 기능 요약 (3~4개)",
                    "items": {"type": "string"}
                },
                "notImplemented": {
                    "type": "array",
                    "description": "타인 구현 기능 (2~3개)",
                    "items": {"type": "string"}
                }
            },
            "required": ["implemented", "notImplemented"]
        },
        "codeInsights": {
            "type": "array",
            "description": "심층 코드 인사이트 (최대 2~3개)",
            "items": {
                "type": "object",
                "properties": {
                    "number": {"type": "number"},
                    "title": {"type": "string"},
                    "points": {
                        "type": "array",
                        "description": "핵심 포인트 (2~3개)",
                        "items": {"type": "string"}
                    },
                    "codeLocation": {
                        "type": "array",
                        "description": "관련 핵심 파일 (1~2개)",
                        "items": {"type": "string"}
                    }
                },
                "required": ["number", "title", "points", "codeLocation"]
            }
        }
    },
    "required": [
        "techstacks",
        "implementedFeatures",
        "keyImplementations",
        "projectSummary",
        "codeInsights"
    ]
}
