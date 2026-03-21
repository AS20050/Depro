# codeReviewLayer/reviewer.py
import json
from codeReviewLayer.analyzers.repo_scanner import scan_repo
from codeReviewLayer.analyzers.structure_analyzer import infer_structure
from codeReviewLayer.analyzers.dependency_analyzer import analyze_dependencies
from codeReviewLayer.llm.repo_reasoner import reason_about_repo
from codeReviewLayer.prompts import REPO_REASONING_PROMPT

def review_project(project_path: str):
    # 1. Gather Data
    repo_scan = scan_repo(project_path)
    structure = infer_structure(repo_scan)
    dependencies = analyze_dependencies(project_path)

    # 2. Prepare Summary for AI
    repo_summary = {
        "structure": structure,
        "dependencies": dependencies,
        "repo_scan": {
            "directories": repo_scan["directories"][:30],
            "files": repo_scan["files"][:50]
        }
    }

    # 3. Format Prompt
    prompt = REPO_REASONING_PROMPT.format(
        repo_data=json.dumps(repo_summary, indent=2)
    )

    # 4. Get AI Response (Now guaranteed to be a Dict)
    ai_reasoning = reason_about_repo(prompt)
    
    # 5. Return Combined Result
    return {
        "repo_structure": structure,
        "dependencies": dependencies,
        "ai_understanding": ai_reasoning
    }