# codeReviewLayer/reviewer.py

import json
from codeReviewLayer.analyzers.repo_scanner import scan_repo
from codeReviewLayer.analyzers.structure_analyzer import infer_structure
from codeReviewLayer.analyzers.dependency_analyzer import analyze_dependencies
from codeReviewLayer.llm.repo_reasoner import reason_about_repo
from codeReviewLayer.prompts import REPO_REASONING_PROMPT


def review_project(project_path: str) -> dict:
    print(f"🔍 [REVIEW] Scanning: {project_path}")

    # 1. Gather data
    repo_scan    = scan_repo(project_path)
    structure    = infer_structure(repo_scan)
    dependencies = analyze_dependencies(project_path)

    print(f"   Files: {repo_scan['total_files']} | "
          f"Algorand signals: {len(repo_scan['algorand_signals'])}")

    # 2. Build summary for AI
    repo_summary = {
        "structure": structure,
        "dependencies": dependencies,
        "algorand_signals": repo_scan["algorand_signals"],
        "is_algorand_project_pre_check": dependencies.get("is_algorand_project", False),
        "peeked_files": repo_scan.get("peeked_files", {}),
        "repo_scan": {
            "directories": repo_scan["directories"][:40],
            "files": [
                {"path": f["path"], "extension": f["extension"]}
                for f in repo_scan["files"][:80]
            ]
        }
    }

    # 3. Pre-check: log if Algorand signals found
    if repo_summary["algorand_signals"]:
        print(f"   ⚡ Algorand signals detected: {repo_summary['algorand_signals']}")

    # 4. Format prompt and call AI
    prompt = REPO_REASONING_PROMPT.format(
        repo_data=json.dumps(repo_summary, indent=2)
    )

    ai_reasoning = reason_about_repo(prompt)

    # 5. Post-process: if pre-check says Algorand but AI missed it, correct it
    if (repo_summary["is_algorand_project_pre_check"]
            and not ai_reasoning.get("is_algorand_dapp")):
        print("   ⚠️  AI missed Algorand signals — applying correction.")
        ai_reasoning["project_type"]    = "algorand_dapp"
        ai_reasoning["is_algorand_dapp"] = True

        # Try to populate contract_file from structure analyzer
        algo_struct = structure.get("algorand_structure", {})
        if not ai_reasoning.get("contract_file"):
            ai_reasoning["contract_file"] = algo_struct.get("contract_file")
        if not ai_reasoning.get("frontend_dir"):
            ai_reasoning["frontend_dir"] = algo_struct.get("frontend_dir")
        if not ai_reasoning.get("algorand_framework"):
            ai_reasoning["algorand_framework"] = algo_struct.get("framework", "unknown")

    print(f"   ✅ Classified as: {ai_reasoning.get('project_type')} "
          f"({ai_reasoning.get('language')})")

    return {
        "repo_structure": structure,
        "dependencies":   dependencies,
        "ai_understanding": ai_reasoning
    }