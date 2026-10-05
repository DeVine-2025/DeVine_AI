"""
Infra & DevOps Detector (인프라 및 환경 설정 감지 모듈)

비즈니스 로직(TS/TSX/PY 등)에 밀려 Docker, CI/CD, Terraform,
Nginx, 패키지 설정 등 인프라/DevOps 관련 중요 기여가 누락되는 문제를 방지합니다.
"""

import os
import re
from typing import Dict, Any, Tuple, List

INFRA_EXACT_NAMES = {
    "dockerfile", "docker-compose.yml", "docker-compose.yaml",
    "package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock",
    "tsconfig.json", "tsconfig.app.json", "tsconfig.node.json",
    "vite.config.ts", "vite.config.js", "next.config.js", "next.config.mjs", "next.config.ts",
    "pyproject.toml", "requirements.txt", "setup.py", "poetry.lock",
    "pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle",
    "build.sh", "deploy.sh", "start.sh", "entrypoint.sh",
    "nginx.conf", "caddyfile", "procfile", "vercel.json", "netlify.toml",
    ".gitlab-ci.yml", ".travis.yml", "jenkinsfile",
}

INFRA_EXTENSIONS = {
    ".tf", ".tfvars", ".hcl", ".tfstate",
    ".yaml", ".yml", ".sh", ".bash", ".zsh",
    ".conf", ".ini", ".toml", ".env.example"
}

INFRA_PATH_KEYWORDS = {
    "workflows", "github/workflows", "gitlab-ci",
    "iac", "oci", "aws", "gcp", "azure", "terraform",
    "k8s", "kubernetes", "helm", "ansible",
    "docker", "deploy", "infra", "infrastructure",
    "scripts", "ops", "monitoring"
}


def is_infra_file(file_path: str) -> bool:
    """주어진 파일 경로가 인프라/빌드/설정/DevOps 파일인지 판정"""
    normalized = file_path.replace("\\", "/").lower()
    filename = os.path.basename(normalized)
    ext = os.path.splitext(filename)[1]

    # 1. 파일명 정확 일치 (예: Dockerfile, package.json, build.sh)
    if filename in INFRA_EXACT_NAMES or filename.startswith("dockerfile"):
        return True

    # 2. 특정 디렉토리 경로 포함 (예: .github/workflows/, iac/, oci/, aws/)
    parts = normalized.split("/")
    for part in parts[:-1]:
        if part in INFRA_PATH_KEYWORDS or part.startswith(".github"):
            return True

    # 3. 인프라 전용 확장자 (.tf, .hcl 등)
    if ext in {".tf", ".tfvars", ".hcl"}:
        return True

    # 4. config/settings 류 파일
    if "config" in filename or "setting" in filename:
        if ext in {".json", ".ts", ".js", ".py", ".yaml", ".yml"}:
            return True

    return False


def partition_file_changes(
    files: Dict[str, Any]
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    수정된 파일 목록을 비즈니스 로직 파일과 인프라/설정 파일로 이원화 분리합니다.
    
    Returns:
        (business_files, infra_files)
    """
    business_files: Dict[str, Any] = {}
    infra_files: Dict[str, Any] = {}

    for path, data in files.items():
        if is_infra_file(path):
            infra_files[path] = data
        else:
            business_files[path] = data

    return business_files, infra_files
