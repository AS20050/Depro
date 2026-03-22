# codeReviewLayer/analyzers/repo_scanner.py

from pathlib import Path
import json

EXCLUDED_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "dist", "build", ".next", ".nuxt", "out", "coverage",
    ".idea", ".vscode", "target", ".gradle"
}

# Files whose content we peek at to give the AI real data
PEEK_FILES = {
    "package.json", "requirements.txt", "pom.xml",
    "algokit.toml", "application.json", "arc32.json",
    "Dockerfile", "docker-compose.yml", "pyproject.toml"
}

# Algorand-specific signals we actively look for
ALGORAND_SIGNALS = {
    "files": ["algokit.toml", "application.json", "arc32.json", ".algokit.toml"],
    "extensions": [".teal"],
    "dir_keywords": ["smart_contracts", "contracts", "artifacts"],
    "import_keywords": ["pyteal", "algopy", "algokit", "beaker", "algosdk"]
}


def _peek_file(path: Path) -> str:
    """Read first 500 chars of a file for AI context."""
    try:
        return path.read_text(errors="ignore")[:500]
    except Exception:
        return ""


def _check_algorand_import(path: Path) -> bool:
    """Check if a .py file imports Algorand libraries."""
    try:
        content = path.read_text(errors="ignore")[:2000]
        return any(kw in content for kw in ALGORAND_SIGNALS["import_keywords"])
    except Exception:
        return False


def scan_repo(project_path: str) -> dict:
    base = Path(project_path)

    files = []
    directories = []
    peeked_files = {}
    algorand_signals = []

    for path in base.rglob("*"):
        # Skip excluded directories
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue

        relative = str(path.relative_to(base))

        if path.is_dir():
            directories.append(relative)

            # Check directory name for Algorand signals
            dir_name = path.name.lower()
            if any(kw in dir_name for kw in ALGORAND_SIGNALS["dir_keywords"]):
                algorand_signals.append(f"dir:{relative}")

        elif path.is_file():
            entry = {
                "path": relative,
                "extension": path.suffix,
                "size_bytes": path.stat().st_size
            }
            files.append(entry)

            # Peek at important config files
            if path.name in PEEK_FILES:
                peeked_files[relative] = _peek_file(path)

            # Algorand signal: .teal files
            if path.suffix == ".teal":
                algorand_signals.append(f"teal_file:{relative}")

            # Algorand signal: known filenames
            if path.name in ALGORAND_SIGNALS["files"]:
                algorand_signals.append(f"config:{relative}")

            # Algorand signal: .py files that import Algorand libs
            if path.suffix == ".py" and _check_algorand_import(path):
                algorand_signals.append(f"algorand_import:{relative}")

    return {
        "directories": directories,
        "files": files,
        "peeked_files": peeked_files,
        "algorand_signals": algorand_signals,
        "total_files": len(files),
        "total_dirs": len(directories)
    }