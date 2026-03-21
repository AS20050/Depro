# codeReviewLayer/schema.py
from pydantic import BaseModel
from typing import List

class AIReviewResponse(BaseModel):
    project_overview: str
    technical_analysis: str
    key_features: List[str]
    improvement_suggestions: List[str]
    rating: int
    project_type: str
    language: str
    entry_point: str
    dependencies: List[str]