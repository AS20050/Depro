# codeReviewLayer/schema.py

from pydantic import BaseModel, Field
from typing import List, Optional

class AIReviewResponse(BaseModel):
    # ── Core identification ──────────────────────────────
    project_overview: str
    technical_analysis: str
    project_type: str           # "frontend" | "backend" | "fullstack" | "algorand_dapp"
    project_sub_type: str       # "react" | "vue" | "fastapi" | "express" | "puya" | "pyteal" | "unknown"
    language: str               # "python" | "node" | "java" | "static" | "unknown"
    entry_point: Optional[str] = None

    # ── Quality metadata ────────────────────────────────
    key_features: List[str]
    improvement_suggestions: List[str]
    rating: int
    dependencies: List[str]

    # ── Algorand-specific (populated only for algorand_dapp) ──
    is_algorand_dapp: bool = False
    contract_file: Optional[str] = None       # e.g. "smart_contracts/hello/contract.py"
    frontend_dir: Optional[str] = None        # e.g. "frontend/" or "ui/"
    has_abi_spec: bool = False                # True if application.json / arc32.json exists
    algorand_framework: Optional[str] = None  # "puya" | "pyteal" | "beaker" | "unknown"