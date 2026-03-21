from pathlib import Path

def analyze_dependencies(project_path: str):
    base = Path(project_path)

    deps = {
        "languages": set(),
        "libraries": set(),
        "frameworks": set()
    }

    if (base / "requirements.txt").exists():
        deps["languages"].add("python")
        content = (base / "requirements.txt").read_text(errors="ignore")
        for line in content.splitlines():
            if line.strip():
                deps["libraries"].add(line.split("==")[0])

    if (base / "package.json").exists():
        deps["languages"].add("javascript")
        import json
        pkg = json.loads((base / "package.json").read_text())
        for k in ["dependencies", "devDependencies"]:
            if k in pkg:
                deps["libraries"].update(pkg[k].keys())

    return {
        "languages": list(deps["languages"]),
        "libraries": list(deps["libraries"]),
        "frameworks": []  # inferred later by AI
    }
