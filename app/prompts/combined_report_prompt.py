COMBINED_REPORT_PROMPT = """
You are an expert at analyzing software project contributions and writing comprehensive reports.
IMPORTANT: You must write all the values within the JSON response in KOREAN (한국어).

The following is the contribution analysis for "{author_name}" in the repository "{repo_url}".

=== Project Information ===
Repository: {repo_url}
Total Commits: {total_commits}
Commits by {author_name}: {user_commits}
Contribution Ratio: {contribution_ratio}%

=== Tech Stack ===
{tech_stack}

=== Available Techstack Enum Values ===
{available_techstacks}

=== Project Scale ===
Total Code Files: {total_files}
Total Lines of Code: {total_lines}
Development Period: {development_period}
Test Code Files: {test_code_count}

=== Project Structure ===
{tree_structure}

=== Code Change Statistics for {author_name} ===
Total Lines Added: {lines_added}
Total Lines Deleted: {lines_deleted}
Files Modified: {files_modified}

=== Commit Messages by {author_name} ===
{commit_messages}

=== Files Modified and Code Changes by {author_name} ===
{file_changes}

=== Other Contributors ===
{other_contributors}

Based on the information above, analyze the contribution of "{author_name}" and provide a main report (summary), a detailed report, AND a techstacks array (only the techstacks that "{author_name}" personally used based on their commits and code changes) in the following JSON format.

{{
    "techstacks": ["techstack enums that {author_name} directly used"],
    "main": {{
        "overview": {{
            "summary": "프로젝트 목적과 해결하는 문제 (2-3문장)",
            "mainTech": "핵심 프레임워크/언어 요약 (예: Java 백엔드 서버 개발 (Spring Boot))",
            "capabilities": ["이 프로젝트를 통해 증명된 5개 핵심 역량"],
            "scale": "코드 라인, 파일 수, 기간 요약 (예: 약 15,000줄 코드 작성, 85개 파일, 6개월 개발)"
        }},
        "projectInfo": {{
            "projectName": "레포지토리 기반 프로젝트명",
            "techStack": ["상세 기술 스택 리스트 (예: Java 17, Spring Boot 3.2, PostgreSQL)"],
            "scale": "{total_lines}줄 | {total_files}개 파일 | {development_period} 개발 기간"
        }},
        "keyImplementations": [
            {{
                "title": "핵심 기능명 (예: 토스뱅크 API 자동 검증 시스템)",
                "description": "상세 구현 방법 및 로직 (3-4줄)",
                "capabilities": ["이 기능에서 얻은 4개 구체적 기술 역량"]
            }}
        ],
        "aiEvaluation": [
            {{
                "title": "전문가 평가 키워드 (예: 실무 중심 백엔드 개발자)",
                "details": ["코드 샘플과 구조 기반 3개 상세 평가 포인트"]
            }}
        ],
        "recommendations": ["추천 서비스 도메인 또는 직무 3개 (예: 금융/결제 서비스 백엔드 개발)"]
    }},
    "detail": {{
        "reportTitle": "프로젝트명 (영문 또는 한글)",
        "reportSubtitle": "프로젝트 상세 분석 리포트",
        "projectOverview": {{
            "purpose": "프로젝트 목적 상세 설명 (2-3문장, 무엇을 해결하는지)",
            "techStack": [
                {{"title": "카테고리명", "content": "실제 사용된 기술들 나열"}}
            ],
            "projectScale": {{
                "mainCodeFiles": {total_files},
                "totalCodeLines": {total_lines},
                "developmentPeriod": "{development_period}",
                "architecturePattern": "아키텍처 패턴 (예: 3계층 아키텍처, MSA 등)"
            }}
        }},
        "implementedFeatures": [
            {{
                "category": "기능 카테고리 (예: 보안 및 인증 시스템)",
                "categoryNumber": 1,
                "features": [
                    {{
                        "name": "세부 기능명 (예: JWT 토큰 인증 시스템)",
                        "implementation": ["구현 내용 (큰 틀)"],
                        "codeLocation": [
                            "src/main/java/security/JwtTokenProvider.java"
                        ],
                        "details": ["세부 구현 내용"]
                    }}
                ]
            }}
        ],
        "projectSummary": {{
            "implemented": ["{author_name}이(가) 이 레포지토리에서 직접 구현한 기능"],
            "notImplemented": ["이 레포지토리에 존재하지만 다른 개발자가 구현한 기능"]
        }},
        "codeInsights": [
            {{
                "number": 1,
                "title": "인사이트 제목 (예: 아키텍처 패턴)",
                "points": ["분석 포인트"],
                "codeLocation": ["관련 코드 위치"]
            }}
        ],
        "improvements": [
            {{
                "number": 1,
                "title": "개선 영역 (예: 데이터베이스 쿼리 최적화)",
                "currentState": ["현재 상태 설명"],
                "suggestions": ["개선 방향 및 제안"],
                "keywords": "학습 키워드 (예: JPA N+1 문제)"
            }}
        ],
        "nextSteps": [
            {{
                "number": 1,
                "title": "다음 프로젝트 제안 (예: 비동기 처리)",
                "description": ["제안 설명"]
            }}
        ]
    }}
}}

Important Requirements:
- The "main" section should be a concise summary suitable for quick overview.
- The "detail" section should contain comprehensive analysis with specific code locations.
- Ensure consistency between main and detail sections - they must describe the same project coherently.
- Analyze commit messages and code changes to identify the specific features actually implemented by {author_name}.
- For projectSummary:
  - "implemented" = features actually built by {author_name} in this repository
  - "notImplemented" = features in this repository built by OTHER contributors (NOT {author_name})
  - NEVER include missing technology stack (e.g., "no frontend" in backend repo, "no backend" in frontend repo, "no database" etc.)
  - Only list features that EXIST in the codebase but were implemented by other people
- Group implemented features by category (e.g., Security, File Processing, API Integration, etc.).
- Write code locations based on the actual project structure provided.
- **Array Length Guidelines**:
  - main.overview.capabilities: Provide exactly 5 items
  - main.projectInfo.techStack: Provide 5-10 items
  - main.keyImplementations: Provide exactly 4 items
  - main.keyImplementations[].capabilities: Provide exactly 4 items
  - main.aiEvaluation: Provide exactly 3 items
  - main.aiEvaluation[].details: Provide exactly 3 items
  - main.recommendations: Provide exactly 3 items
  - detail.implementedFeatures: Provide up to 5 categories
  - detail.implementedFeatures[].features: Provide 2-4 items per category
  - detail.implementedFeatures[].features[].implementation: Provide 2-3 items
  - detail.implementedFeatures[].features[].details: Provide 2-3 items
  - detail.projectSummary.implemented: Provide 3-5 items
  - detail.projectSummary.notImplemented: Provide 1-3 items
  - detail.codeInsights: Provide exactly 4 items
  - detail.codeInsights[].points: Provide 2-3 items
  - detail.improvements: Provide exactly 3 items
  - detail.improvements[].currentState: Provide 1-2 items
  - detail.improvements[].suggestions: Provide 2-3 items
  - detail.nextSteps: Provide exactly 3 items
  - detail.nextSteps[].description: Provide 2-3 items
- **techStack Rules (IMPORTANT)**:
  - Include as many applicable categories as possible based on the project.
  - ONLY include categories where actual technologies are used in the project. Do NOT include empty or irrelevant categories.
  - Available categories (include ONLY if applicable):
    - "백엔드": Only if backend code exists (Java, Spring, Express, Django, etc.)
    - "프론트엔드": Only if frontend code exists (React, Vue, Angular, HTML/CSS/JS, etc.)
    - "데이터베이스": Only if database-related code exists (SQL, ORM, Redis, etc.)
    - "라이브러리": Only if external libraries are used
    - "외부 서비스": Only if external APIs or cloud services are called
    - "도구": Only if specific build tools, package managers, or dev tools are used
    - "보안": Only if security features are implemented (JWT, OAuth, encryption, etc.)
  - Consider adding specific categories like "테스트", "배포", "인프라", "상태관리", "스타일링" if applicable to the project.
- Respond strictly in JSON format only.
- **techstacks Rules (CRITICAL)**:
  - The "techstacks" field must be a string array containing ONLY values from the "Available Techstack Enum Values" section above.
  - Select ONLY the techstacks that "{author_name}" actually used based on their commits, code changes, and modified files — NOT the entire project's tech stack.
  - Do NOT include techstacks that "{author_name}" did not directly work with, even if the project uses them.
  - Do NOT include root position values (BACKEND, FRONTEND, INFRA) - only include specific technologies.
  - Return exact enum names as strings (e.g., "JAVA", "SPRINGBOOT", "REACT", "TYPESCRIPT").
  - Example: If "{author_name}" worked on Java backend with Spring Boot and MySQL queries, return ["JAVA", "SPRINGBOOT", "MYSQL"].
"""


from typing import List, Optional


def get_combined_report_prompt(
    repo_url: str,
    author_name: str,
    total_commits: int,
    user_commits: int,
    contribution_ratio: float,
    tech_stack: str,
    total_files: int,
    total_lines: int,
    tree_structure: str,
    lines_added: int,
    lines_deleted: int,
    files_modified: int,
    commit_messages: str,
    file_changes: str,
    other_contributors: str,
    development_period: str,
    test_code_count: int,
    available_techstacks: Optional[List[str]] = None
) -> str:
    techstacks_str = ", ".join(available_techstacks) if available_techstacks else "No techstacks provided"

    return COMBINED_REPORT_PROMPT.format(
        repo_url=repo_url,
        author_name=author_name,
        total_commits=total_commits,
        user_commits=user_commits,
        contribution_ratio=contribution_ratio,
        tech_stack=tech_stack,
        total_files=total_files,
        total_lines=total_lines,
        tree_structure=tree_structure,
        lines_added=lines_added,
        lines_deleted=lines_deleted,
        files_modified=files_modified,
        commit_messages=commit_messages,
        file_changes=file_changes,
        other_contributors=other_contributors,
        development_period=development_period,
        test_code_count=test_code_count,
        available_techstacks=techstacks_str
    )
