import traceback
from mcpServer.infraScripts.amplify_cicd import connect_amplify_repo_ex

def connect_amplify_cicd(repo_url: str, github_token: str, app_name: str = "opsonic-cicd"):
    """
    MCP Tool: Connects GitHub repo to Amplify for Auto-Deployment (CI/CD).
    """
    print(f"🔧 [TOOL] connect_amplify_cicd called for: {repo_url}")

    try:
        result = connect_amplify_repo_ex(repo_url, github_token, app_name)
        
        return {
            "status": "success",
            "deployment": "aws_amplify_cicd",
            "app_id": result["app_id"],
            "endpoint": result["url"],
            "message": "CI/CD Pipeline Established. Future commits will auto-deploy."
        }
    except Exception as e:
        print("❌ [TOOL] Error trace:")
        traceback.print_exc()
        return {"status": "error", "message": str(e)}