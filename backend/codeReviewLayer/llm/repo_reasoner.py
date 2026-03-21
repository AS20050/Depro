import os
import json
from ollama import Client
from codeReviewLayer.schema import AIReviewResponse

# Initialize Ollama Client with your custom host
# We don't need an API key for standard Ollama, just the host.
client = Client(host='https://ai.live.melp.us/ollama')

def reason_about_repo(prompt: str) -> dict:
    """
    Sends the prompt to your custom Ollama server using the 'gpt-oss' model.
    Enforces JSON output to match the Pydantic schema.
    """
    
    # 1. Prepare the System Prompt
    system_instruction = (
        "You are a Senior Code Reviewer. "
        "You must output a valid JSON object matching this structure: "
        "{\"project_overview\": str, \"technical_analysis\": str, "
        "\"key_features\": [str], \"improvement_suggestions\": [str], \"rating\": int}"
    )

    try:
        # 2. Call Ollama with format='json'
        # This is the "magic switch" that forces valid JSON output
        response = client.chat(
            model='gpt-oss:20b',
            messages=[
                {'role': 'system', 'content': system_instruction},
                {'role': 'user', 'content': prompt},
            ],
            format='json',  # <--- CRITICAL: Enforces JSON mode
            options={
                'temperature': 0.2
            }
        )
        
        # 3. Extract content
        raw_content = response['message']['content']
        
        # 4. Parse JSON string to Dict
        data = json.loads(raw_content)
        
        # 5. Validate against Pydantic Schema
        validated_data = AIReviewResponse(**data)
        
        return validated_data.model_dump()

    except json.JSONDecodeError:
        print(f"Ollama JSON Error. Raw output: {raw_content[:100]}...")
        return {
            "project_overview": "Error: AI response was not valid JSON.",
            "technical_analysis": "Could not parse response.",
            "key_features": [],
            "improvement_suggestions": [],
            "rating": 0
        }
    except Exception as e:
        print(f"Ollama Connection Error: {e}")
        return {
            "project_overview": "Internal Error during AI processing.",
            "technical_analysis": f"Ollama Error: {str(e)}",
            "key_features": [],
            "improvement_suggestions": [],
            "rating": 0
        }