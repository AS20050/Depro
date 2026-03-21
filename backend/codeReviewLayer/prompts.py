REPO_REASONING_PROMPT = """
You are a Senior DevOps Architect. Analyze the provided repository structure and content.

CRITICAL OUTPUT INSTRUCTIONS:
1. Identify if this is a 'frontend', 'backend', or 'fullstack' project.
2. Detect the primary language: 'python', 'node', 'java', or 'static'.
3. **Find the Entry Point**:
   - For Python/FastAPI: Look for 'main.py', 'app.py', or where 'FastAPI()' is initialized.
   - For Node.js: Look for 'index.js', 'server.js', or the 'start' script in package.json.
   - Return the filename (e.g., "main.py") or command (e.g., "npm start").

Return a valid JSON object matching this schema exactly:
{{
  "project_overview": "Summary...",
  "technical_analysis": "Deep dive...",
  "key_features": ["feature1", "feature2"],
  "improvement_suggestions": ["suggestion1"],
  "rating": 8,
  "project_type": "backend",
  "language": "python",
  "entry_point": "main.py",
  "dependencies": ["fastapi", "uvicorn"]
}}

REPOSITORY DATA:
{repo_data}
"""