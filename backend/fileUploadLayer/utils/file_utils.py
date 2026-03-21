from pathlib import Path

EXCLUDED_DIRS = {".git", "node_modules", "__pycache__", ".venv"}

def get_project_files(base_path: str, max_files: int = 50):
    files = []
    base = Path(base_path)

    for path in base.rglob("*"):
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        if path.is_file():
            files.append(str(path))
        if len(files) >= max_files:
            break

    return files
