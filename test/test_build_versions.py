import json
import os

from app.utils.build_versions import clean_version, parse_build_versions


def _write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def test_package_json_dependencies_and_dev(tmp_path):
    _write(tmp_path, "package.json", json.dumps({
        "dependencies": {"react": "^19.1.1", "next": "15.3.0"},
        "devDependencies": {"typescript": "~5.4.2", "eslint": "latest"},
    }))
    v = parse_build_versions(str(tmp_path), ["package.json"])
    assert v["react"] == "19.1.1"
    assert v["next"] == "15.3.0"
    assert v["typescript"] == "5.4.2"
    assert "eslint" not in v  # 숫자 버전이 아니면 버린다


def test_root_package_json_wins_over_nested(tmp_path):
    _write(tmp_path, "package.json", json.dumps({"dependencies": {"react": "19.1.1"}}))
    _write(tmp_path, "apps/web/package.json", json.dumps({"dependencies": {"react": "18.2.0", "zustand": "4.5.0"}}))
    v = parse_build_versions(str(tmp_path), ["apps/web/package.json", "package.json"])
    assert v["react"] == "19.1.1"
    assert v["zustand"] == "4.5.0"


def test_build_gradle_plugins_java_and_deps(tmp_path):
    _write(tmp_path, "build.gradle", """
plugins {
    id 'java'
    id 'org.springframework.boot' version '3.4.1'
    id 'io.spring.dependency-management' version '1.1.7'
}
java { toolchain { languageVersion = JavaLanguageVersion.of(21) } }
dependencies {
    implementation 'org.springframework.boot:spring-boot-starter-web'
    implementation "io.jsonwebtoken:jjwt-api:0.12.6"
    runtimeOnly 'com.mysql:mysql-connector-j'
}
""")
    v = parse_build_versions(str(tmp_path), ["build.gradle"])
    assert v["org.springframework.boot"] == "3.4.1"
    assert v["java"] == "21"
    assert v["jjwt-api"] == "0.12.6"


def test_requirements_and_pyproject(tmp_path):
    _write(tmp_path, "requirements.txt", "fastapi>=0.133,<1\npydantic==2.12.5\n# comment\nuvicorn[standard]\nopenai >= 1.0.0\n")
    _write(tmp_path, "pyproject.toml", '[project]\nrequires-python = ">=3.11"\ndependencies = ["httpx==0.28.1", "google-genai>=2.19"]\n')
    v = parse_build_versions(str(tmp_path), ["requirements.txt", "pyproject.toml"])
    assert "fastapi" not in v and "openai" not in v  # 하한(>=)은 실제 버전이 아니므로 쓰지 않는다
    assert v["pydantic"] == "2.12.5"
    assert "uvicorn" not in v
    assert v["httpx"] == "0.28.1"
    assert "google-genai" not in v
    assert v["python"] == "3.11"


def test_node_modules_ignored(tmp_path):
    _write(tmp_path, "node_modules/x/package.json", json.dumps({"dependencies": {"left-pad": "1.0.0"}}))
    v = parse_build_versions(str(tmp_path), ["node_modules/x/package.json"])
    assert v == {}


def test_clean_version():
    assert clean_version("^1.2.3") == "1.2.3"
    assert clean_version(">=0.133,<1") == "0.133"
    assert clean_version("workspace:*") is None
    assert clean_version("npm:@scope/pkg@2.0.0") == "2.0.0"
