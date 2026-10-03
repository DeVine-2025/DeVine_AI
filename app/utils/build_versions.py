"""HEAD 빌드 파일에서 의존성 버전 표를 뽑는다.

결과는 `{dep_key: version}`이다. LLM은 의존성 키(`react`, `org.springframework.boot`)만 고르고,
버전 문자열은 코드가 이 표로 채운다. 같은 키가 여러 파일에 있으면 경로가 얕은 파일(루트)이 이긴다.
"""
import json
import os
import re
import tomllib
from typing import Dict, Iterable, Optional

BUILD_FILES = {"package.json", "build.gradle", "build.gradle.kts", "requirements.txt", "pyproject.toml"}
_SKIP_PARTS = {"node_modules", "vendor", "dist", "build", ".venv", "venv"}
_VERSION = re.compile(r"\d+(?:\.\d+)*")


def clean_version(spec: str) -> Optional[str]:
    """`^1.2.3`, `>=0.133,<1`, `npm:pkg@2.0.0` 같은 표기에서 첫 숫자 버전만 남긴다."""
    if not isinstance(spec, str):
        return None
    if spec.startswith("npm:") and "@" in spec[5:]:
        spec = spec.rsplit("@", 1)[1]
    if spec.startswith(("workspace:", "file:", "link:", "git", "http")):
        return None
    m = _VERSION.search(spec)
    return m.group(0) if m else None


def _package_json(text: str) -> Dict[str, str]:
    data = json.loads(text)
    out = {}
    for section in ("dependencies", "devDependencies"):
        for name, spec in (data.get(section) or {}).items():
            v = clean_version(spec)
            if v:
                out.setdefault(name, v)
    return out


def _gradle(text: str) -> Dict[str, str]:
    out = {}
    for m in re.finditer(r"id\s*\(?\s*['\"]([\w.\-]+)['\"]\s*\)?\s*version\s*['\"]([^'\"]+)['\"]", text):
        out[m.group(1)] = clean_version(m.group(2)) or m.group(2)
    m = re.search(r"languageVersion\s*=\s*JavaLanguageVersion\.of\(\s*(\d+)\s*\)", text) or re.search(
        r"sourceCompatibility\s*=\s*['\"]?(?:JavaVersion\.VERSION_)?(\d+(?:[._]\d+)?)", text
    )
    if m:
        out["java"] = m.group(1).replace("_", ".")
    for m in re.finditer(r"['\"]([\w.\-]+):([\w.\-]+):([\w.\-]+)['\"]", text):
        v = clean_version(m.group(3))
        if v:
            out.setdefault(m.group(2), v)
    return out


def _requirements(text: str) -> Dict[str, str]:
    out = {}
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        # 정확히 고정한 버전(==)만 쓴다. >=, ~= 는 하한이라 실제 설치 버전과 다를 수 있다(P5 버전 오류)
        m = re.match(r"([A-Za-z0-9_.\-]+)(?:\[[^\]]*\])?\s*(===?)\s*([^,;\s]+)", line)
        if m:
            v = clean_version(m.group(3))
            if v:
                out.setdefault(m.group(1).lower(), v)
    return out


def _pyproject(text: str) -> Dict[str, str]:
    data = tomllib.loads(text)
    out = {}
    project = data.get("project") or {}
    if project.get("requires-python"):
        v = clean_version(project["requires-python"])
        if v:
            out["python"] = v
    out.update(_requirements("\n".join(project.get("dependencies") or [])))
    poetry = ((data.get("tool") or {}).get("poetry") or {}).get("dependencies") or {}
    for name, spec in poetry.items():
        spec = spec.get("version") if isinstance(spec, dict) else spec
        v = clean_version(spec or "")
        if v:
            out.setdefault("python" if name == "python" else name.lower(), v)
    return out


_PARSERS = {
    "package.json": _package_json,
    "build.gradle": _gradle,
    "build.gradle.kts": _gradle,
    "requirements.txt": _requirements,
    "pyproject.toml": _pyproject,
}


def parse_build_versions(dir_path: str, tracked_files: Iterable[str]) -> Dict[str, str]:
    candidates = [
        f for f in tracked_files
        if os.path.basename(f) in BUILD_FILES and not (set(f.split("/")) & _SKIP_PARTS)
    ]
    versions: Dict[str, str] = {}
    for rel in sorted(candidates, key=lambda p: (p.count("/"), p)):
        try:
            with open(os.path.join(dir_path, rel), encoding="utf-8") as f:
                parsed = _PARSERS[os.path.basename(rel)](f.read())
        except Exception:
            continue
        for key, version in parsed.items():
            versions.setdefault(key, version)
    return versions


def format_versions_table(versions: Dict[str, str], limit: int = 120) -> str:
    if not versions:
        return "(빌드 파일에서 버전 정보를 찾지 못함)"
    return "\n".join(f"- {k}: {v}" for k, v in list(versions.items())[:limit])
