# Stage 2: Insight & Synthesis Analysis Schema

INSIGHT_SCHEMA = {
    "type": "object",
    "properties": {
        "overview": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "mainTech": {"type": "string"},
                "capabilities": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "scale": {"type": "string"}
            },
            "required": ["summary", "mainTech", "capabilities", "scale"]
        },
        "projectInfo": {
            "type": "object",
            "properties": {
                "projectName": {"type": "string"},
                "techStack": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "scale": {"type": "string"}
            },
            "required": ["projectName", "techStack", "scale"]
        },
        "aiEvaluation": {
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
        "recommendations": {
            "type": "array",
            "items": {"type": "string"}
        },
        "projectOverview": {
            "type": "object",
            "properties": {
                "purpose": {"type": "string"},
                "techStack": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "content": {"type": "string"}
                        },
                        "required": ["title", "content"]
                    }
                },
                "projectScale": {
                    "type": "object",
                    "properties": {
                        "mainCodeFiles": {"type": "number"},
                        "totalCodeLines": {"type": "number"},
                        "developmentPeriod": {"type": "string"},
                        "architecturePattern": {"type": "string"}
                    },
                    "required": ["mainCodeFiles", "totalCodeLines", "developmentPeriod", "architecturePattern"]
                }
            },
            "required": ["purpose", "techStack", "projectScale"]
        },
        "improvements": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "number": {"type": "number"},
                    "title": {"type": "string"},
                    "currentState": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "suggestions": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "keywords": {"type": "string"}
                },
                "required": ["number", "title", "currentState", "suggestions", "keywords"]
            }
        },
        "nextSteps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "number": {"type": "number"},
                    "title": {"type": "string"},
                    "description": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "recommendKeyword": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                },
                "required": ["number", "title", "description", "recommendKeyword"]
            }
        }
    },
    "required": [
        "overview",
        "projectInfo",
        "aiEvaluation",
        "recommendations",
        "projectOverview",
        "improvements",
        "nextSteps"
    ]
}
