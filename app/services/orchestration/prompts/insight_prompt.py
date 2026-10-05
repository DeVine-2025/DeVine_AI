# Stage 2: Insight & Synthesis Prompt

INSIGHT_ANALYSIS_PROMPT = """\
You are an executive engineering manager and principal tech evaluator.
Based on the verified technical contributions of "{author_name}" in the repository "{repo_url}", synthesize a high-level developer evaluation and architectural insight report.

=== Project Scale & Metadata ===
Repository: {repo_url}
Total Files: {total_files}
Total Code Lines: {total_lines}
Development Period: {development_period}
Technologies Used by {author_name}: {author_techstacks}

=== Verified Key Implementations by {author_name} (Extracted & Audited) ===
{key_implementations_summary}

=== Verified Features by {author_name} ===
{verified_features_summary}

=== Project Contribution Summary ===
Implemented by {author_name}:
{implemented_summary}

Implemented by other team members:
{not_implemented_summary}

============================================================
EVALUATION & SYNTHESIS INSTRUCTIONS:
============================================================
1. COHERENCE WITH STAGE 1 FINDINGS:
   - Your evaluation, improvements, and next steps must be logically grounded in the verified features and code insights provided above.
   - Do NOT contradict the verified facts. Do NOT invent new libraries or frameworks that were not used.

2. DEPTH & TECHNICAL ACCURACY:
   - "aiEvaluation": provide 3 sharp, professional titles evaluating {author_name}'s strengths as an engineer, with 3 concrete details for each.
   - "improvements": highlight 3 specific technical areas where {author_name}'s code or architecture could be elevated (e.g. concurrency, query optimization, architectural modularity, error resilience), with current state, suggestions, and keywords.
   - "nextSteps": suggest 3 practical next projects or technical deep-dives to advance their skills.

3. ARRAY LENGTH REQUIREMENTS:
   - overview.capabilities: exactly 5 items.
   - projectInfo.techStack: 5 to 10 items representing the overall project technologies.
   - aiEvaluation: exactly 3 items, each with title and exactly 3 details.
   - recommendations: exactly 3 items.
   - improvements: exactly 3 items, each with 1-2 currentState and 2-3 suggestions.
   - nextSteps: exactly 3 items, each with 2-3 description and 2-3 recommendKeyword.

Respond in valid JSON conforming to the requested schema. Write all descriptive text in Korean (한국어).
"""


def get_insight_analysis_prompt(
    repo_url: str,
    author_name: str,
    total_files: int,
    total_lines: int,
    development_period: str,
    author_techstacks: str,
    key_implementations_summary: str,
    verified_features_summary: str,
    implemented_summary: str,
    not_implemented_summary: str,
) -> str:
    return INSIGHT_ANALYSIS_PROMPT.format(
        repo_url=repo_url,
        author_name=author_name,
        total_files=total_files,
        total_lines=total_lines,
        development_period=development_period,
        author_techstacks=author_techstacks,
        key_implementations_summary=key_implementations_summary,
        verified_features_summary=verified_features_summary,
        implemented_summary=implemented_summary,
        not_implemented_summary=not_implemented_summary,
    )
