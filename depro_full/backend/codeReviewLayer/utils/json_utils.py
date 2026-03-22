# codeReviewLayer/utils/json_utils.py
import json
import re

def extract_json(text):
    """
    Robustly extracts JSON from a string, handling Markdown code blocks 
    and extraneous text often returned by LLMs.
    """
    try:
        # 1. Try simple json.loads first (best case)
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. Look for markdown code blocks ```json ... ```
    match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        json_str = match.group(1)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass
    
    # 3. Look for the first outer curly braces { ... }
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        json_str = match.group(0)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass

    # 4. Fallback: If parsing fails, return a partial error dict so the app doesn't crash 500
    print(f"FAILED TO EXTRACT JSON FROM:\n{text}")
    return {
        "project_overview": "Error parsing AI response",
        "technical_analysis": "The AI returned a response that could not be parsed as JSON.",
        "rating": 0
    }