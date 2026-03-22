# codeReviewLayer/analyzers/structure_analyzer.py

from pathlib import Path


FRONTEND_KEYWORDS = ["frontend", "client", "web", "ui", "app", "webapp", "www"]
BACKEND_KEYWORDS  = ["backend", "server", "api", "service", "src"]
CONTRACT_KEYWORDS = ["smart_contracts", "contracts", "contract", "artifacts", "teal"]


def _names(items: list) -> list:
    """Extract just the bottom-level name from paths."""
    return [Path(i).name.lower() for i in items]


def infer_structure(repo_scan: dict) -> dict:
    dirs  = repo_scan["directories"]
    files = repo_scan["files"]
    algorand_signals = repo_scan.get("algorand_signals", [])

    dir_names  = _names(dirs)
    file_names = _names([f["path"] for f in files])
    extensions = {f["extension"] for f in files}

    structure = {
        "frontend_dirs":  [],
        "backend_dirs":   [],
        "contract_dirs":  [],
        "shared_files":   [],
        "has_dockerfile": False,
        "is_monorepo":    False,
        "algorand_structure": {
            "detected": False,
            "signals":  algorand_signals,
            "contract_file": None,
            "frontend_dir": None,
            "has_abi_spec": False,
            "framework": None
        }
    }

    # ── Directory classification ─────────────────────────
    for d in dirs:
        d_lower = Path(d).name.lower()
        if any(k in d_lower for k in CONTRACT_KEYWORDS):
            structure["contract_dirs"].append(d)
        elif any(k in d_lower for k in FRONTEND_KEYWORDS):
            structure["frontend_dirs"].append(d)
        elif any(k in d_lower for k in BACKEND_KEYWORDS):
            structure["backend_dirs"].append(d)

    # ── File signals ─────────────────────────────────────
    if "Dockerfile" in file_names or "docker-compose.yml" in file_names:
        structure["has_dockerfile"] = True

    # Monorepo: has both frontend AND (backend OR contracts)
    if structure["frontend_dirs"] and (
        structure["backend_dirs"] or structure["contract_dirs"]
    ):
        structure["is_monorepo"] = True

    # ── Algorand-specific structure ──────────────────────
    algo = structure["algorand_structure"]

    if algorand_signals:
        algo["detected"] = True

        # Detect framework from signals
        for signal in algorand_signals:
            if "algopy" in signal or "puya" in signal.lower():
                algo["framework"] = "puya"
                break
            if "pyteal" in signal or "beaker" in signal:
                algo["framework"] = "pyteal"
                break

        # Find contract file from signals
        for signal in algorand_signals:
            if signal.startswith("algorand_import:") or signal.startswith("teal_file:"):
                algo["contract_file"] = signal.split(":", 1)[1]
                break

        # Find ABI spec
        for f in files:
            if f["path"].endswith("application.json") or f["path"].endswith("arc32.json"):
                algo["has_abi_spec"] = True
                break

        # Find frontend dir within dApp repo
        for d in dirs:
            if any(k in d.lower() for k in FRONTEND_KEYWORDS):
                algo["frontend_dir"] = d
                break

    # ── Shared file classification ───────────────────────
    for f in files:
        ext = f["extension"]
        path = f["path"]
        if ext in [".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".env"]:
            structure["shared_files"].append(path)

    return structure