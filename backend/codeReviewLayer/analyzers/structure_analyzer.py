def infer_structure(repo_scan):
    dirs = repo_scan["directories"]
    files = repo_scan["files"]

    structure = {
        "frontend": [],
        "backend": [],
        "shared": [],
        "unknown": []
    }

    for d in dirs:
        d_lower = d.lower()
        if any(k in d_lower for k in ["frontend", "client", "web", "ui"]):
            structure["frontend"].append(d)
        elif any(k in d_lower for k in ["backend", "server", "api"]):
            structure["backend"].append(d)
        else:
            structure["unknown"].append(d)

    for f in files:
        ext = f["extension"]
        if ext in [".js", ".ts", ".jsx", ".tsx"]:
            structure["frontend"].append(f["path"])
        elif ext in [".py", ".java", ".go"]:
            structure["backend"].append(f["path"])
        else:
            structure["shared"].append(f["path"])

    return structure
