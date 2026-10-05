# Stage 1: Feature Extraction Prompt (v3 with AST, Metadata, Infra Guard)

FEATURE_EXTRACTION_PROMPT = """당신은 개발자의 Git 커밋 히스토리와 코드 변경사항을 분석하여 구현 기능, 인프라 기여, 기술 스택을 정확하게 추출하는 전문 테크니컬 리드 분석관입니다.

다음 정보를 바탕으로 {author_name} 개발자의 기여 내용을 정밀하게 분석하십시오.

## 프로젝트 정보
- 저장소: {repo_url}
- 분석 대상: {author_name}
- 커밋 기여: 전체 {total_commits}개 중 {user_commits}개 ({contribution_ratio:.1f}%)
- 추가/삭제: +{lines_added:,} / -{lines_deleted:,} 라인
- 변경 파일 수: {files_modified}개

## 전체 변경 규모 및 통계 메타데이터 (Scale & Scope)
{change_metadata}

## 감지된 기술 스택
{tech_stack}

## 프로젝트 디렉터리 구조
{tree_structure}

## 커밋 메시지 히스토리
{commit_messages}

## 주요 비즈니스 로직 코드 변경 내역 (Diff)
{file_changes}

## 인프라 및 빌드/배포 환경 설정 변경 내역 (Dedicated Infra Diff)
{infra_changes}

## 다른 기여자 현황 (본인 기여와 엄격히 구분할 것)
{other_contributors}

---

## 분석 지침 (엄격 준수)

1. **전체 변경 규모 및 메타데이터 (migrationMeta)**:
   - 개발자가 수정한 전체 파일 수와 디렉토리 분포를 확인하십시오.
   - 30개 이상의 파일 또는 광범위한 리팩토링이 확인될 경우, 'isLargeScale': true로 설정하고, 대표적인 15~25개 파일을 선별한 배경 맥락을 'scopeDescription'에 명시하십시오.

2. **인프라 및 환경 설정 기여 (infraAndDevOps)**:
   - '인프라 및 빌드/배포 환경 설정 변경 내역'에 Docker, CI/CD, Terraform, Nginx, 패키지 설정(package.json 등), 빌드 스크립트 등의 기여가 있는 경우 이를 독립적으로 포착하십시오.
   - 인프라 기여가 명확한 경우 'hasInfraWork': true로 설정하고 사용 기술, 기여 요약, 핵심 파일을 작성하십시오. (해당 작업이 없으면 false)

3. **구현 기능 (implementedFeatures) 수량 상한선 준수**:
   - 카테고리 수: **최대 3~4개**로 엄격히 제한하십시오.
   - 카테고리당 기능 수: **최대 2~3개**로 제한하십시오.
   - **codeLocation 경로 엄격성**: 기능당 **가장 핵심적인 1~3개의 실제 코드 파일 경로만** 기재하십시오. (아이콘, 단순 CSS, 락파일은 배제하고 컴포넌트/훅/API/비즈니스로직 파일 위주로 선정)
   - 전체 리포트에 포함되는 총 코드 경로는 **15~25개 내외로 집중**하십시오.

4. **기술 스택 (techstacks)**:
   - {author_name} 개발자가 **직접 작성하거나 수정한 코드에서 실제로 사용한 기술**만 선택하십시오.

5. **본인 vs 타인 기여 구분 (myFeatures / otherFeatures)**:
   - {author_name} 개발자가 직접 구현한 기능과 다른 기여자가 구현한 기능을 명확히 구분하십시오.

결과는 반드시 지정된 JSON 스키마를 엄격히 준수하여 출력하십시오.
"""


def get_feature_analysis_prompt(
    repo_url: str,
    author_name: str,
    total_commits: int,
    user_commits: int,
    contribution_ratio: float,
    tech_stack: str,
    tree_structure: str,
    lines_added: int,
    lines_deleted: int,
    files_modified: int,
    commit_messages: str,
    file_changes: str,
    other_contributors: str,
    change_metadata: str = "",
    infra_changes: str = "",
    available_techstacks: list = None,
) -> str:
    return FEATURE_EXTRACTION_PROMPT.format(
        repo_url=repo_url,
        author_name=author_name,
        total_commits=total_commits,
        user_commits=user_commits,
        contribution_ratio=contribution_ratio,
        tech_stack=tech_stack,
        tree_structure=tree_structure,
        lines_added=lines_added,
        lines_deleted=lines_deleted,
        files_modified=files_modified,
        commit_messages=commit_messages,
        file_changes=file_changes,
        infra_changes=infra_changes or "(인프라 및 환경 설정 파일 변경 내역 없음)",
        other_contributors=other_contributors,
        change_metadata=change_metadata or "(메타데이터 없음)",
    )
