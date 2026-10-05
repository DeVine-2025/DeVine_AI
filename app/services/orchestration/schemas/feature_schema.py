# Stage 1: Feature & Code Analysis Schema
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
            "description": "구현 기능 카테고리 목록 (3~5개)",
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "categoryNumber": {"type": "number"},
                    "features": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "implementation": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                },
                                "codeLocation": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                },
                                "details": {
                                    "type": "array",
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
            "items": {"type": "string"}
        },
        "otherFeatures": {
            "type": "array",
            "items": {"type": "string"}
        }
    },
    "required": [
        "techstacks",
        "implementedFeatures",
        "keyImplementations",
        "codeInsights",
        "myFeatures",
        "otherFeatures"
    ]
}
