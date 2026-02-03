import os
import json
from typing import Dict, List


def detect_tech_stack(dir_path: str) -> Dict[str, List[str]]:
    tech_stack = {
        "languages": [],
        "frameworks": [],
        "libraries": [],
        "databases": [],
        "tools": []
    }

    extension_to_language = {
        ".py": "Python",
        ".js": "JavaScript",
        ".jsx": "JavaScript (React)",
        ".ts": "TypeScript",
        ".tsx": "TypeScript (React)",
        ".java": "Java",
        ".kt": "Kotlin",
        ".swift": "Swift",
        ".go": "Go",
        ".rs": "Rust",
        ".rb": "Ruby",
        ".php": "PHP",
        ".cs": "C#",
        ".cpp": "C++",
        ".c": "C",
        ".vue": "Vue.js",
        ".svelte": "Svelte"
    }

    language_counts = {}
    for root, dirs, files in os.walk(dir_path):
        dirs[:] = [d for d in dirs if d not in ["node_modules", "vendor", ".git", "__pycache__", "venv"]]

        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in extension_to_language:
                lang = extension_to_language[ext]
                language_counts[lang] = language_counts.get(lang, 0) + 1

    tech_stack["languages"] = sorted(language_counts.keys(), key=lambda x: language_counts[x], reverse=True)

    package_json_path = os.path.join(dir_path, "package.json")
    if os.path.exists(package_json_path):
        _parse_package_json(package_json_path, tech_stack)

    requirements_path = os.path.join(dir_path, "requirements.txt")
    if os.path.exists(requirements_path):
        _parse_requirements_txt(requirements_path, tech_stack)

    pyproject_path = os.path.join(dir_path, "pyproject.toml")
    if os.path.exists(pyproject_path):
        _parse_pyproject_toml(pyproject_path, tech_stack)

    _detect_tools(dir_path, tech_stack)

    for key in tech_stack:
        tech_stack[key] = list(dict.fromkeys(tech_stack[key]))

    return tech_stack


def _parse_package_json(path: str, tech_stack: Dict[str, List[str]]):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        all_deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}

        framework_map = {
            "next": "Next.js",
            "react": "React",
            "vue": "Vue.js",
            "nuxt": "Nuxt.js",
            "express": "Express.js",
            "fastify": "Fastify",
            "koa": "Koa",
            "@nestjs/core": "NestJS",
            "@angular/core": "Angular",
            "svelte": "Svelte",
            "gatsby": "Gatsby",
            "remix": "Remix"
        }

        library_map = {
            "axios": "Axios",
            "lodash": "Lodash",
            "dayjs": "Day.js",
            "moment": "Moment.js",
            "redux": "Redux",
            "zustand": "Zustand",
            "prisma": "Prisma",
            "@prisma/client": "Prisma",
            "mongoose": "Mongoose",
            "sequelize": "Sequelize",
            "typeorm": "TypeORM",
            "tailwindcss": "Tailwind CSS",
            "styled-components": "Styled Components"
        }

        db_map = {
            "pg": "PostgreSQL",
            "mysql": "MySQL",
            "mysql2": "MySQL",
            "mongodb": "MongoDB",
            "redis": "Redis",
            "sqlite3": "SQLite"
        }

        for dep in all_deps:
            if dep in framework_map:
                tech_stack["frameworks"].append(framework_map[dep])
            if dep in library_map:
                tech_stack["libraries"].append(library_map[dep])
            if dep in db_map:
                tech_stack["databases"].append(db_map[dep])

    except Exception:
        pass


def _parse_requirements_txt(path: str, tech_stack: Dict[str, List[str]]):
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().lower()

        python_frameworks = {
            "django": "Django",
            "flask": "Flask",
            "fastapi": "FastAPI",
            "tornado": "Tornado"
        }

        python_libs = {
            "pandas": "Pandas",
            "numpy": "NumPy",
            "tensorflow": "TensorFlow",
            "torch": "PyTorch",
            "scikit-learn": "Scikit-learn",
            "sqlalchemy": "SQLAlchemy",
            "celery": "Celery"
        }

        for line in content.split("\n"):
            pkg = line.split("==")[0].split(">=")[0].split("[")[0].strip()

            if pkg in python_frameworks:
                tech_stack["frameworks"].append(python_frameworks[pkg])
            if pkg in python_libs:
                tech_stack["libraries"].append(python_libs[pkg])

    except Exception:
        pass


def _parse_pyproject_toml(path: str, tech_stack: Dict[str, List[str]]):
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().lower()

        if "fastapi" in content:
            tech_stack["frameworks"].append("FastAPI")
        if "django" in content:
            tech_stack["frameworks"].append("Django")
        if "flask" in content:
            tech_stack["frameworks"].append("Flask")

    except Exception:
        pass


def _detect_tools(dir_path: str, tech_stack: Dict[str, List[str]]):
    if os.path.exists(os.path.join(dir_path, "Dockerfile")) or \
       os.path.exists(os.path.join(dir_path, "docker-compose.yml")):
        tech_stack["tools"].append("Docker")

    if os.path.exists(os.path.join(dir_path, ".github", "workflows")):
        tech_stack["tools"].append("GitHub Actions")

    if os.path.exists(os.path.join(dir_path, ".gitlab-ci.yml")):
        tech_stack["tools"].append("GitLab CI")

    if os.path.exists(os.path.join(dir_path, "Jenkinsfile")):
        tech_stack["tools"].append("Jenkins")

    if os.path.exists(os.path.join(dir_path, "vercel.json")) or \
       os.path.exists(os.path.join(dir_path, ".vercel")):
        tech_stack["tools"].append("Vercel")
