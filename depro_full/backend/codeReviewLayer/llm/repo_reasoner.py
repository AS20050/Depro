# codeReviewLayer/llm/repo_reasoner.py

import os
import json
from ollama import Client
from codeReviewLayer.schema import AIReviewResponse

client = Client(host='https://ai.live.melp.us/ollama')

SYSTEM_INSTRUCTION = (
    "You are a Senior DevOps Architect. "
    "Analyse repository data and return ONLY a valid JSON object with these exact keys: "
    "project_overview (str), technical_analysis (str), key_features (list[str]), "
    "improvement_suggestions (list[str]), rating (int 1-10), "
    "project_type (str: frontend|backend|fullstack|algorand_dapp|unknown), "
    "project_sub_type (str), language (str: python|node|java|static|unknown), "
    "entry_point (str or null), dependencies (list[str]), "
    "is_algorand_dapp (bool), contract_file (str or null), "
    "frontend_dir (str or null), has_abi_spec (bool), "
    "algorand_framework (str or null). "
    "No markdown. No explanation. JSON only."
)

DEFAULT_FALLBACK = {
    "project_overview": "Could not analyse project.",
    "technical_analysis": "AI response could not be parsed.",
    "key_features": [],
    "improvement_suggestions": [],
    "rating": 0,
    "project_type": "unknown",
    "project_sub_type": "unknown",
    "language": "unknown",
    "entry_point": None,
    "dependencies": [],
    "is_algorand_dapp": False,
    "contract_file": None,
    "frontend_dir": None,
    "has_abi_spec": False,
    "algorand_framework": None
}


def reason_about_repo(prompt: str) -> dict:
    """
    Sends the prompt to the Ollama server.
    Returns a validated dict conforming to AIReviewResponse schema.
    """
    raw_content = ""

    try:
        response = client.chat(
            model='gpt-oss:20b',
            messages=[
                {'role': 'system', 'content': SYSTEM_INSTRUCTION},
                {'role': 'user',   'content': prompt},
            ],
            format='json',
            options={'temperature': 0.1}  # Lower temp = more deterministic JSON
        )

        raw_content = response['message']['content']
        data = json.loads(raw_content)

        # Inject defaults for any missing Algorand fields
        # (older models may omit new fields)
        for key, default in DEFAULT_FALLBACK.items():
            if key not in data:
                data[key] = default

        validated = AIReviewResponse(**data)
        return validated.model_dump()

    except json.JSONDecodeError:
        print(f"⚠️  JSON parse error. Raw: {raw_content[:200]}")
        return DEFAULT_FALLBACK.copy()

    except Exception as e:
        print(f"⚠️  Ollama error: {e}")
        return DEFAULT_FALLBACK.copy()