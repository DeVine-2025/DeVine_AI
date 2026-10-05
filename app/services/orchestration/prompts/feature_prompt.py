# Stage 1: Feature & Code Analysis Prompt

FEATURE_ANALYSIS_PROMPT = """\
You are an expert software engineer and code auditor.
Your mission is to perform a strict, fact-based code analysis of contributions made by "{author_name}" in the repository "{repo_url}".

=== Repository Information ===
Repository: {repo_url}
Total Commits: {total_commits}
Commits by {author_name}: {user_commits}
Contribution Ratio: {contribution_ratio:.1f}%

=== Detected Tech Stack & Enums ===
Detected Tech Stack:
{tech_stack}

Available Techstack Enum Values:
{available_techstacks}

=== Project Structure (Full Depth) ===
{tree_structure}

=== Code Change Statistics for {author_name} ===
Total Lines Added: {lines_added}
Total Lines Deleted: {lines_deleted}
Files Modified: {files_modified}

=== Commit Messages by {author_name} ===
{commit_messages}

=== Files Modified and Code Diffs/Changes by {author_name} ===
{file_changes}

=== Other Contributors ===
{other_contributors}

============================================================
CRITICAL INSTRUCTIONS & ACCURACY RULES:
============================================================
1. FACT-BASED ONLY (NO HALLUCINATION):
   - Only describe features that {author_name} ACTUALLY implemented based on the commit messages and code changes provided.
   - Do NOT invent or exaggerate features that are not explicitly present in the code diffs or commit history.
   - If {author_name} only fixed a bug or styled a component, describe exactly that. Do NOT claim they built the entire subsystem.

2. STRICT AUTHOR ATTRIBUTION (DO NOT ATTRIBUTE OTHER'S WORK):
   - Examine "Other Contributors" and file diffs carefully.
   - If a file or architecture was created by another contributor and {author_name} only imported or modified a small part, clearly distinguish it.
   - In "projectSummary":
     - "implemented": list 3 to 5 features that {author_name} personally built.
     - "notImplemented": list 1 to 3 features in this repository that were built by OTHER contributors (NOT {author_name}).

3. ACCURATE FILE PATHS (CRITICAL):
   - Every "codeLocation" path MUST EXACTLY MATCH a real file path present in the "Project Structure" tree above.
   - Do NOT use shortened paths, aliases, or guess non-existent directories.
   - Do NOT reference files that were deleted or renamed in past commits if they no longer exist in the current project structure.

4. STRICT ARRAY BOUNDS & QUANTITY CAPS (STRICT BOUNDS - DO NOT EXCEED):
   - keyImplementations: exactly 2 to 3 items, each with title, description, and 2 to 3 capabilities.
   - implementedFeatures: exactly 3 to 4 categories, each with 2 to 3 features.
   - implementedFeatures[].features[].codeLocation: exactly 1 to 3 KEY files only. Do NOT list minor helper files, secondary types, or icons.
   - TOTAL codeLocation paths across the entire report MUST BE BETWEEN 15 AND 25 FILES. Do NOT exceed 25 file paths in total.
   - projectSummary.implemented: exactly 3 to 4 items.
   - projectSummary.notImplemented: exactly 2 to 3 items.
   - codeInsights: exactly 2 to 3 items, each with 2 to 3 points and 1 to 2 key codeLocation paths.
   - techstacks: array of enum strings that {author_name} directly used (e.g. ["TYPESCRIPT", "REACT", "NEXTJS"]).

Respond in valid JSON conforming to the requested schema. Write all descriptive text in Korean (한국어).
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
    available_techstacks: list = None,
) -> str:
    techstacks_str = (
        ", ".join(available_techstacks)
        if available_techstacks
        else "No techstacks provided"
    )

    return FEATURE_ANALYSIS_PROMPT.format(
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
        other_contributors=other_contributors,
        available_techstacks=techstacks_str,
    )
