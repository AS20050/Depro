# codeReviewLayer/analyzers/dependency_analyzer.py

from pathlib import Path
import json

ALGORAND_LIBS = {
    "pyteal", "beaker", "algopy", "algokit-utils",
    "algokit_utils", "algosdk", "py-algorand-sdk"
}

FRONTEND_FRAMEWORKS = {
    "react", "vue", "svelte", "angular", "next",
    "nuxt", "astro", "solid-js", "remix"
}

BACKEND_FRAMEWORKS = {
    "fastapi", "flask", "django", "express",
    "nestjs", "hono", "koa", "gin"
}


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(errors="ignore"))
    except Exception:
        return {}


def _read_lines(path: Path) -> list:
    try:
        return [l.strip() for l in path.read_text(errors="ignore").splitlines() if l.strip()]
    except Exception:
        return []


def analyze_dependencies(project_path: str) -> dict:
    base = Path(project_path)

    result = {
        "languages": set(),
        "libraries": set(),
        "frameworks": set(),
        "algorand_libs": set(),
        "is_algorand_project": False,
        "frontend_framework": None,
        "backend_framework": None,
        "has_algokit_toml": False,
        "build_tool": None
    }

    # ── Python: requirements.txt ─────────────────────────
    for req_file in base.rglob("requirements.txt"):
        if any(p in EXCLUDED for p in req_file.parts):
            continue
        result["languages"].add("python")
        for line in _read_lines(req_file):
            name = line.split("==")[0].split(">=")[0].split("~=")[0].strip().lower()
            if name:
                result["libraries"].add(name)
                if name in ALGORAND_LIBS:
                    result["algorand_libs"].add(name)
                if name in BACKEND_FRAMEWORKS:
                    result["backend_framework"] = name
                    result["frameworks"].add(name)

    # ── Python: pyproject.toml ───────────────────────────
    for pyproj in base.rglob("pyproject.toml"):
        if any(p in EXCLUDED for p in pyproj.parts):
            continue
        content = pyproj.read_text(errors="ignore")
        result["languages"].add("python")
        for lib in ALGORAND_LIBS:
            if lib in content:
                result["algorand_libs"].add(lib)

    # ── Algorand: algokit.toml ───────────────────────────
    algokit_toml = base / "algokit.toml"
    if algokit_toml.exists():
        result["has_algokit_toml"] = True
        result["is_algorand_project"] = True
        result["languages"].add("python")

    # ── Node: package.json (recursive for monorepos) ─────
    for pkg_file in base.rglob("package.json"):
        if any(p in EXCLUDED for p in pkg_file.parts):
            continue
        pkg = _read_json(pkg_file)
        result["languages"].add("javascript")

        all_deps = {}
        all_deps.update(pkg.get("dependencies", {}))
        all_deps.update(pkg.get("devDependencies", {}))

        for dep in all_deps:
            dep_lower = dep.lower().lstrip("@").split("/")[-1]
            result["libraries"].add(dep)

            if dep_lower in FRONTEND_FRAMEWORKS:
                result["frontend_framework"] = dep_lower
                result["frameworks"].add(dep_lower)
            if dep_lower in BACKEND_FRAMEWORKS:
                result["backend_framework"] = dep_lower
                result["frameworks"].add(dep_lower)

        # Build tool detection
        if "vite" in all_deps:
            result["build_tool"] = "vite"
        elif "webpack" in all_deps:
            result["build_tool"] = "webpack"

        # Scripts can hint at project type
        scripts = pkg.get("scripts", {})
        if "start" in scripts or "dev" in scripts:
            result["libraries"].add("__has_dev_script__")

    # ── Java: pom.xml ────────────────────────────────────
    pom = base / "pom.xml"
    if pom.exists():
        result["languages"].add("java")
        result["frameworks"].add("maven")

    # ── Java: build.gradle ───────────────────────────────
    gradle = base / "build.gradle"
    if gradle.exists():
        result["languages"].add("java")
        result["frameworks"].add("gradle")

    # Determine if Algorand project
    if result["algorand_libs"] or result["has_algokit_toml"]:
        result["is_algorand_project"] = True

    return {
        "languages": list(result["languages"]),
        "libraries": list(result["libraries"]),
        "frameworks": list(result["frameworks"]),
        "algorand_libs": list(result["algorand_libs"]),
        "is_algorand_project": result["is_algorand_project"],
        "has_algokit_toml": result["has_algokit_toml"],
        "frontend_framework": result["frontend_framework"],
        "backend_framework": result["backend_framework"],
        "build_tool": result["build_tool"]
    }


EXCLUDED = {
    ".git", "node_modules", "__pycache__", ".venv",
    "venv", "dist", "build", ".next", "target"
}