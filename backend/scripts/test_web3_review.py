"""
Test script: Run the code review pipeline on the demo Algorand dApp.
Does NOT deploy anything — just verifies detection works.

Usage:
    cd backend
    python scripts/test_web3_review.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure backend root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
load_dotenv()

from codeReviewLayer.reviewer import review_project


DEMO_DAPP_PATH = str(Path(__file__).resolve().parents[2] / "algorand" / "demo_dapp")
# Fallback: also check backend/storage test data
FALLBACK_PATH = str(Path(__file__).resolve().parents[1] / "storage" / "extracted" / "zip" / "test_dapp")


def main():
    # Pick whichever demo path exists
    path = DEMO_DAPP_PATH
    if not Path(path).exists():
        path = FALLBACK_PATH
    if not Path(path).exists():
        print(f"ERROR: No demo dApp found at:\n  {DEMO_DAPP_PATH}\n  {FALLBACK_PATH}")
        sys.exit(1)

    print(f"Reviewing: {path}\n")
    result = review_project(path)

    print("\n" + "=" * 60)
    print("REVIEW RESULT")
    print("=" * 60)
    print(json.dumps(result, indent=2, default=str))

    # Verify Algorand detection
    ai = result.get("ai_understanding", {})
    deps = result.get("dependencies", {})

    print("\n" + "=" * 60)
    print("ALGORAND DETECTION CHECK")
    print("=" * 60)
    print(f"  project_type:        {ai.get('project_type')}")
    print(f"  is_algorand_dapp:    {ai.get('is_algorand_dapp')}")
    print(f"  algorand_framework:  {ai.get('algorand_framework')}")
    print(f"  contract_file:       {ai.get('contract_file')}")
    print(f"  frontend_dir:        {ai.get('frontend_dir')}")
    print(f"  has_abi_spec:        {ai.get('has_abi_spec')}")
    print(f"  is_algorand_project: {deps.get('is_algorand_project')}")
    print(f"  algorand_libs:       {deps.get('algorand_libs')}")

    if ai.get("project_type") == "algorand_dapp" or ai.get("is_algorand_dapp"):
        print("\n  PASS: Algorand dApp correctly detected!")
    else:
        print("\n  FAIL: Not detected as algorand_dapp")
        sys.exit(1)


if __name__ == "__main__":
    main()
