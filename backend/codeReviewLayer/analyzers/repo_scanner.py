from pathlib import Path

EXCLUDED_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"
}

def scan_repo(project_path: str):
    base = Path(project_path)

    files = []
    directories = []

    for path in base.rglob("*"):
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue

        if path.is_dir():
            directories.append(str(path.relative_to(base)))
        elif path.is_file():
            files.append({
                "path": str(path.relative_to(base)),
                "extension": path.suffix
            })

    return {
        "directories": directories,
        "files": files
    }
