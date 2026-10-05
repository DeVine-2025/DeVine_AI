"""섹션 작성 에이전트 지시문과 입력 조립.

주의: ADK는 instruction 안의 중괄호 표현을 세션 상태 치환으로 해석한다. 지시문에 중괄호를 쓰지 않는다.
"""
import json
from typing import Dict, List

from app.report.context import ReportContext
from app.report.engines.shared.evidence import VerifiedFeature

LANG = "모든 값은 한국어로 쓴다."

TECH_INSTRUCTION = f"""너는 개발자 리포트의 기술 스택 섹션 작성자다. 입력은 빌드 파일 의존성 표, 자동 감지된 스택, 작성자가 수정한 파일 목록, techstacks enum 목록이다.
규칙:
- techstacks: 작성자가 직접 사용한 기술만 enum에서 고른다. 근거는 작성자가 수정한 파일의 확장자·경로와 의존성이다. 프로젝트에만 있고 작성자가 다루지 않은 기술은 고르지 않는다.
- projectTech: 프로젝트 전체의 주요 기술 5~10개. 의존성 표에 있는 기술은 dep에 그 키를 정확히 넣는다. 의존성 표에 없는 기술(언어, 런타임, 인프라)은 dep을 none으로 둔다. 버전은 서버가 채우므로 name에 버전 숫자를 쓰지 않는다.
- overviewGroups: 실제로 쓰인 카테고리만 만든다. 카테고리 이름은 백엔드, 프론트엔드, 데이터베이스, 라이브러리, 외부 서비스, 도구, 보안, 테스트, 배포, 인프라, 상태관리, 스타일링 중에서 고른다. items의 dep 규칙은 projectTech와 같다.
- 입력에 근거가 없는 기술을 만들지 않는다.
{LANG}"""

FEATURES_INSTRUCTION = f"""너는 개발자 포트폴리오 리포트의 '구현 기능' 섹션 작성자다. 입력은 코드로 검증된 기능 목록(K-ID), 기여 수준, 다른 기여자가 주로 만든 파일 목록(O-ID)이다.
규칙:
- categories: 기능을 성격별 카테고리 최대 5개로 묶는다. 카테고리마다 기능 2~4개. 각 기능은 입력의 K-ID 하나를 fid로 가리키고, 같은 K-ID를 두 번 쓰지 않는다. 입력에 없는 기능을 만들지 않는다.
- name은 입력 기능명을 다듬어도 되지만 뜻을 바꾸지 않는다.
- implementation(2~3개)은 큰 틀의 구현 방법, details(2~3개)는 세부 구현이다. 입력 요약에 있는 사실만 쓴다. 요약에 없는 기법·수치·라이브러리를 덧붙이지 않는다.
- 수준 표현: created/major 기능은 '구현', '설계'로 쓸 수 있다. minor 기능은 '개선', '수정', '보완'으로 쓰고 '구현했다'고 쓰지 않는다.
- purpose: 이 프로젝트가 무엇을 해결하는지 2~3문장. 프로젝트 이름과 기능 목록에서 드러나는 범위만 쓴다.
- implemented(3~5개): 작성자가 직접 만든 기능을 한 문장씩. created/major 기능 위주.
- notImplemented(0~3개): 이 레포에 있지만 다른 기여자가 만든 기능. 반드시 근거 O-ID를 file_id로 붙인다. 근거가 없으면 쓰지 않는다. '백엔드 없음'처럼 기술이 없다는 말은 쓰지 않는다.
{LANG}"""

INSIGHTS_INSTRUCTION = f"""너는 시니어 개발자로서 작성자 본인에게 주는 코드 피드백 섹션을 쓴다. 입력은 검증된 기능 목록, 코드 관찰(패턴·위험), 기여 수준, 의존성 버전 표다.
규칙:
- codeInsights(4개): 작성자 코드에서 보이는 설계·구현 특징. 각 항목은 구체적인 파일, 함수, 컴포넌트, 라이브러리, 패턴을 짚는다. file_ids에 근거 F-ID를 1~3개 넣는다. points는 2~3개.
- improvements(3개): currentState(1~2개)는 지금 코드의 구체적 상태, suggestions(2~3개)는 무엇을 왜 바꾸고 어떤 대가(트레이드오프)가 있는지 쓴다. 이 프로젝트의 규모와 스택에서 실제로 나은 대안만 쓴다. '테스트 코드 추가', 'CI/CD 도입', '에러 처리 강화'처럼 어느 레포에나 붙는 일반론은 쓰지 않는다. 꼭 필요하면 어느 파일의 어떤 흐름인지 특정한다. keywords는 학습 키워드 한 줄.
- nextSteps(3개): 이 사람의 작업에서 자연스럽게 이어지는 다음 단계. description 2~3개, recommendKeyword 2~3개. 일반적인 학습 목록을 쓰지 않는다.
- architecturePattern: 프로젝트 아키텍처 패턴 한 줄. 입력에서 드러나는 범위만.
- minor 수준 파일은 다른 사람이 주로 쓴 코드일 수 있으므로 작성자의 설계로 평가하지 않는다.
{LANG}"""

MAIN_INSTRUCTION = f"""너는 채용 담당자와 PM이 읽는 요약(main)을 쓴다. 입력은 이미 작성된 상세 리포트(detail)다. 상세 리포트에 없는 사실을 더하지 않는다.
규칙:
- summary: 프로젝트 목적과 작성자가 맡은 부분을 2~3문장으로. 전문 용어는 줄인다.
- mainTech: 핵심 언어·프레임워크 요약 한 줄.
- capabilities(5개): 이 작업으로 확인되는 역량.
- keyImplementations(4개): 상세 리포트의 기능 중 4개를 fid로 고른다(created/major 우선). title, description(무엇을 어떻게 했는지 3~4줄), capabilities(4개).
- aiEvaluation(3개): 평가 키워드 title과 details 3개. 각 detail은 상세 리포트의 구체적 기능이나 인사이트를 근거로 든다. 근거 없는 칭찬을 쓰지 않는다.
- recommendations(3개): 실제 작업 내용에서 나온 추천 서비스 도메인 또는 직무.
{LANG}"""


def _project_header(ctx: ReportContext) -> str:
    f = ctx.facts
    return (
        f"프로젝트: {ctx.project_name} ({ctx.repo_url})\n"
        f"작성자: {ctx.author_name} | 작성자 커밋 {f.author_commit_count}개 / 전체 {f.total_commits}개 ({f.contribution_ratio}%)\n"
        f"작성자 활동 기간: {f.author_first_commit} ~ {f.author_last_commit} ({f.author_period}) | 프로젝트 기간: {f.project_period}\n"
        f"작성자 변경: +{f.author_added} / -{f.author_deleted} 줄, 파일 {f.author_files_modified}개 | 테스트 파일 수(프로젝트): {f.test_files}"
    )


def _file_label(path: str, ledger) -> str:
    own = ledger.files.get(path)
    if not own:
        return path
    share = own.blame_share if own.blame_share is not None else own.author_share
    return f"{path} ({own.level}, 작성자 줄 {share:.0%})"


def format_features_block(feats: List[VerifiedFeature], ledger, idx, max_files: int = 6, with_commits: bool = True) -> str:
    lines = []
    for f in feats:
        lines.append(f"[{f.fid}] {f.name} — 수준: {f.level}")
        for s in f.summaries:
            lines.append(f"  요약: {s}")
        lines.append("  근거 파일: " + ", ".join(f"{idx.path_to_fid.get(p, '')}={_file_label(p, ledger)}" for p in f.paths[:max_files]))
        if with_commits and f.commit_ids:
            msgs = [f"{idx.commit_meta[c]['date']} {idx.commit_meta[c]['message']}" for c in f.commit_ids[:4] if c in idx.commit_meta]
            lines.append("  근거 커밋: " + " / ".join(msgs))
    return "\n".join(lines)


def format_features_input(ctx: ReportContext, feats: List[VerifiedFeature], ledger, idx) -> str:
    owners = {o.path: o for o in ledger.other_owned}
    other_files = "\n".join(
        f"[{oid}] {path} — 주 작성자 {owners[path].owner} ({owners[path].share:.0%})"
        for oid, path in idx.other_ids.items() if path in owners
    ) or "(없음)"
    others = "\n".join(
        f"- {o.name}: {o.commits}커밋 | 주요 디렉터리: {', '.join(o.top_dirs)} | 최근 커밋: {' / '.join(o.recent_subjects[:5])}"
        for o in ctx.other_contributors[:8]
    ) or "(없음)"
    return (
        f"{_project_header(ctx)}\n\n=== 검증된 기능 (작성자) ===\n{format_features_block(feats, ledger, idx)}\n\n"
        f"=== 다른 기여자가 주로 만든 파일 (notImplemented 근거) ===\n{other_files}\n\n=== 다른 기여자 요약 ===\n{others}"
    )


def format_insights_input(ctx: ReportContext, feats: List[VerifiedFeature], ledger, idx, observations: Dict[str, List[str]]) -> str:
    obs = []
    for key, label in (("patterns", "패턴"), ("risks", "위험·개선 여지"), ("notes", "기타 관찰")):
        for o in observations.get(key, [])[:16]:
            obs.append(f"- [{label}] {o}")
    versions = ", ".join(f"{k} {v}" for k, v in list(ctx.build_versions.items())[:60]) or "(없음)"
    return (
        f"{_project_header(ctx)}\n\n=== 검증된 기능 ===\n{format_features_block(feats, ledger, idx, max_files=4, with_commits=False)}\n\n"
        f"=== 코드 관찰 (청크별 근거 카드) ===\n" + ("\n".join(obs) or "(없음)") + f"\n\n=== 의존성 버전 ===\n{versions}"
    )


def format_tech_input(ctx: ReportContext, ledger) -> str:
    versions = "\n".join(f"- {k}: {v}" for k, v in ctx.build_versions.items()) or "(빌드 파일에서 의존성을 찾지 못함)"
    files = sorted(ledger.files.values(), key=lambda o: -o.author_added)[:150]
    file_lines = "\n".join(f"- {o.path} ({o.level})" for o in files) or "(없음)"
    return (
        f"프로젝트: {ctx.project_name}\n\n=== 의존성 표 (dep 키: 버전) ===\n{versions}\n\n"
        f"=== 자동 감지된 스택 ===\n{json.dumps(ctx.tech_stack_detected, ensure_ascii=False)}\n\n"
        f"=== 작성자가 수정한 파일 (많이 쓴 순) ===\n{file_lines}\n\n"
        f"=== techstacks enum ===\n{', '.join(ctx.available_techstacks) or '(제공되지 않음)'}"
    )


def format_main_input(ctx: ReportContext, detail_view: dict) -> str:
    return f"{_project_header(ctx)}\n\n=== 상세 리포트(detail) ===\n{json.dumps(detail_view, ensure_ascii=False, indent=1)}"
