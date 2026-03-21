import os
from mcpServer.infraScripts.deploy_app import deploy_app_node_ex

def deploy_java_app_ec2(artifact_path: str = None): # pyright: ignore[reportArgumentType]
    """
    MCP Tool:
    Uploads and runs a Java JAR on the provisioned EC2 instance.
    Accepts specific artifact_path to deploy dynamically.
    """
    
    # DYNAMIC INJECTION:
    # If a specific file was uploaded, override the .env APP_FILE variable
    # so the underlying script deploys THIS file, not the hardcoded one.
    if artifact_path:
        # infraScripts/deploy_app.py expects just the filename in some places
        # or absolute path in others. Let's ensure env var is correct.
        
        # Update OS Environment for the script to pick up
        os.environ["APP_FILE"] = artifact_path 
        
        # Verify it exists before calling script
        if not os.path.exists(artifact_path):
             return {"status": "error", "message": f"Artifact not found at {artifact_path}"}

    try:
        deploy_app_node_ex()
        
        # We need to fetch the IP/Port again to return the link
        # (Or modify deploy_app_node_ex to return it, but for now we construct it)
        public_ip = os.getenv("EC2_PUBLIC_IP", "your-ec2-ip") # You might need to persist this from provision step
        port = os.getenv("APP_PORT", "8080")

        return {
            "status": "success",
            "deployment": "java_ec2",
            "endpoint": f"http://{public_ip}:{port}",
            "message": "Java application deployed and running"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }