import traceback
from mcpServer.infraScripts.deploy_source import deploy_source_node_ex

def deploy_source_ec2(source_path: str, language: str = "python", entry_point: str = "main.py"):
    """
    MCP Tool: Deploys source code to EC2.
    Supports 'python' (FastAPI/Flask) and 'node' (Express/Next).
    """
    print(f"🔧 [TOOL] deploy_source_ec2 called. Lang: {language}, Entry: {entry_point}")

    try:
        result = deploy_source_node_ex(source_path, language, entry_point)
        
        return {
            "status": "success",
            "deployment": "ec2_source",
            "endpoint": result["endpoint"],
            "public_ip": result["public_ip"],
            "message": result["message"]
        }
    except Exception as e:
        print("❌ [TOOL] Error trace:")
        traceback.print_exc()
        return {"status": "error", "message": str(e)}