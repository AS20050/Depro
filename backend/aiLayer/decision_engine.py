import json
import os
from mcpClient import call_mcp_tool

def decide_and_execute(context: dict):
    """
    Routes execution based on file type or code review analysis.
    Standardizes output so Frontend always receives 'endpoint'.
    """
    print("\n🤔 [DECISION ENGINE] Analyzing Context...")
    
    # 1. Check for Pre-determined Artifacts (JAR)
    if context.get("artifact_type") == "jar":
        jar_path = context.get("artifact_path")
        print(f"🤖 [AI] Artifact detected. Route: Java EC2 Deploy")
        
        # Step 1: Provision
        call_mcp_tool("provision_ec2_instance", {})
        
        # Step 2: Deploy
        deploy_res = call_mcp_tool("deploy_java_app_ec2", {"artifact_path": jar_path})
        
        # 🔥 FIX: Construct Endpoint for Frontend
        public_ip = deploy_res.get("public_ip")
        endpoint = f"http://{public_ip}:8080" if public_ip else None

        return {
            "status": "success",
            "deployment": "ec2_java_artifact",
            "public_ip": public_ip,
            "endpoint": endpoint,  # <--- CRITICAL FOR FRONTEND
            "message": "Java Application Deployed Successfully via EC2."
        }

    # 2. Analyze Code Context
    review = context.get("ai_understanding", {})
    project_type = review.get("project_type", "unknown").lower()
    language = review.get("language", "unknown").lower()
    entry_point = review.get("entry_point", "")
    
    print(f"📊 [DEBUG] Type: {project_type} | Lang: {language} | Entry: {entry_point}")

    # ==========================================
    # PATH B: FRONTEND (Amplify)
    # ==========================================
    if project_type == "frontend" or language == "static":
        print("🤖 [AI] Decision: Frontend detected.")
        
        repo_url = context.get("repo_url")
        github_token = context.get("github_token")
        
        base_name = context.get('filename', 'app').replace(".zip", "").replace(".", "-").split("/")[-1]
        app_name = f"opsonic-{base_name}"

        # Sub-path: CI/CD
        if repo_url and github_token and "github.com" in repo_url:
            print("✨ [PLAN] GitHub Credentials found. Setting up Continuous Deployment.")
            res = call_mcp_tool("connect_amplify_cicd", {
                "repo_url": repo_url,
                "github_token": github_token,
                "app_name": app_name
            })
            # Ensure endpoint key exists
            res["endpoint"] = res.get("url") or res.get("endpoint")
            return res

        # Sub-path: Snapshot
        else:
            print("📸 [PLAN] Zip/No-Token. Performing Snapshot Deployment.")
            
            project_path = context.get("project_path")
            deploy_res = call_mcp_tool("deploy_to_amplify", {
                "source_path": project_path,
                "app_name": app_name
            })
            
            deploy_res["warning"] = "⚠️ SNAPSHOT DEPLOYMENT: This site is static. Future changes will NOT auto-update."
            # Ensure endpoint key exists
            deploy_res["endpoint"] = deploy_res.get("url")
            return deploy_res

    # ==========================================
    # PATH C: BACKEND (EC2 Source)
    # ==========================================
    if project_type in ["backend", "fullstack"]:
        print(f"🤖 [AI] Decision: {language.title()} Backend detected -> EC2 Source Deploy")
        
        print("    1. Provisioning Server...")
        call_mcp_tool("provision_ec2_instance", {})
        
        print(f"    2. Deploying {language} app (Entry: {entry_point})...")
        deploy_res = call_mcp_tool("deploy_source_ec2", {
            "source_path": context.get("project_path"),
            "language": language,
            "entry_point": entry_point
        })
        
        # 🔥 FIX: Construct Endpoint for Frontend
        public_ip = deploy_res.get("public_ip")
        endpoint = f"http://{public_ip}:8080" if public_ip else None
        
        return {
            "status": "success",
            "deployment": "ec2_source_code",
            "public_ip": public_ip,
            "endpoint": endpoint, # <--- CRITICAL FOR FRONTEND
            "message": f"Deployed {language} backend successfully."
        }

    return {"status": "manual", "message": "Unknown project type."}