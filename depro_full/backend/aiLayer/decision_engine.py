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
        provision_res = call_mcp_tool("provision_ec2_instance", {})
        
        # Step 2: Deploy
        deploy_res = call_mcp_tool("deploy_java_app_ec2", {"artifact_path": jar_path})

        # If the tool surfaced an error, propagate it.
        if isinstance(deploy_res, dict) and deploy_res.get("status") == "error":
            return deploy_res

        public_ip = None
        if isinstance(deploy_res, dict):
            public_ip = deploy_res.get("public_ip")
        if not public_ip and isinstance(provision_res, dict):
            public_ip = provision_res.get("public_ip")

        endpoint = None
        if isinstance(deploy_res, dict):
            endpoint = deploy_res.get("endpoint")
        if not endpoint and public_ip:
            endpoint = f"http://{public_ip}:8080"

        if not endpoint:
            return {"status": "error", "message": "Deployment did not return an endpoint (missing public_ip/endpoint)."}

        return {
            "status": "success",
            "deployment": "ec2_java_artifact",
            "public_ip": public_ip,
            "endpoint": endpoint,
            "message": "Java Application Deployed Successfully via EC2.",
        }

    def _find_project_root(start_path: str, marker: str) -> str:
        if not start_path:
            return start_path
        if os.path.exists(os.path.join(start_path, marker)):
            return start_path

        # Search up to a few levels deep for common "zip inside folder" layouts.
        max_depth = 4
        try:
            base_depth = start_path.rstrip(os.sep).count(os.sep)
            for root, dirs, files in os.walk(start_path):
                depth = root.count(os.sep) - base_depth
                if depth > max_depth:
                    dirs[:] = []
                    continue
                if marker in files:
                    return root
        except Exception:
            pass

        return start_path

    def _infer_entry_point(project_path: str, lang: str) -> str:
        if not project_path:
            return ""

        if lang == "python":
            root = _find_project_root(project_path, "requirements.txt")
            for candidate in ["main.py", "app.py", "server.py", "api.py"]:
                if os.path.exists(os.path.join(root, candidate)):
                    return candidate
            return "main.py"

        if lang == "node":
            root = _find_project_root(project_path, "package.json")
            pkg_path = os.path.join(root, "package.json")
            try:
                with open(pkg_path, "r", encoding="utf-8") as f:
                    pkg = json.load(f)
                scripts = pkg.get("scripts", {}) or {}
                if scripts.get("start"):
                    return "npm start"
                if scripts.get("dev"):
                    return "npm run dev"
            except Exception:
                pass

            for candidate in ["index.js", "server.js", "app.js"]:
                if os.path.exists(os.path.join(root, candidate)):
                    return candidate
            return "npm start"

        return ""

    # 2. Analyze Code Context
    review = context.get("ai_understanding", {}) or {}
    project_type = str(review.get("project_type", "unknown")).lower()
    language = str(review.get("language", "unknown")).lower()
    entry_point = review.get("entry_point") or ""

    # Heuristic fallback when LLM classification fails/unavailable.
    if project_type in ("unknown", "", "manual"):
        deps = context.get("dependencies", {}) or {}
        struct = context.get("repo_structure", {}) or {}

        if deps.get("is_algorand_project") or deps.get("has_algokit_toml"):
            return {
                "status": "manual",
                "message": "Algorand project detected. Feature 1 (Algorand dApp deployment) is not implemented yet.",
            }

        frontend_signal = bool(deps.get("frontend_framework") or (struct.get("frontend_dirs") or []))
        backend_signal = bool(deps.get("backend_framework") or (struct.get("backend_dirs") or []))

        if frontend_signal and backend_signal:
            project_type = "fullstack"
        elif frontend_signal:
            project_type = "frontend"
        elif backend_signal:
            project_type = "backend"
        else:
            project_path = context.get("project_path", "")
            if project_path:
                pkg_root = _find_project_root(project_path, "package.json")
                req_root = _find_project_root(project_path, "requirements.txt")
                has_pkg = os.path.exists(os.path.join(pkg_root, "package.json"))
                has_req = os.path.exists(os.path.join(req_root, "requirements.txt"))

                if has_pkg and has_req:
                    project_type = "fullstack"
                elif has_pkg:
                    project_type = "frontend"
                elif has_req:
                    project_type = "backend"
    
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

        if not language or language == "unknown":
            deps = context.get("dependencies", {}) or {}
            langs = set((deps.get("languages") or []))
            if "python" in langs:
                language = "python"
            elif "javascript" in langs:
                language = "node"
            else:
                language = "python"

        if not entry_point:
            entry_point = _infer_entry_point(context.get("project_path", ""), language)

        print("    1. Provisioning Server...")
        provision_res = call_mcp_tool("provision_ec2_instance", {})
        
        print(f"    2. Deploying {language} app (Entry: {entry_point})...")
        deploy_res = call_mcp_tool("deploy_source_ec2", {
            "source_path": context.get("project_path"),
            "language": language,
            "entry_point": entry_point
        })

        if isinstance(deploy_res, dict) and deploy_res.get("status") == "error":
            return deploy_res

        public_ip = None
        if isinstance(deploy_res, dict):
            public_ip = deploy_res.get("public_ip")
        if not public_ip and isinstance(provision_res, dict):
            public_ip = provision_res.get("public_ip")

        endpoint = None
        if isinstance(deploy_res, dict):
            endpoint = deploy_res.get("endpoint")
        if not endpoint and public_ip:
            endpoint = f"http://{public_ip}:8080"

        if not endpoint:
            return {"status": "error", "message": "Source deployment did not return an endpoint."}

        return {
            "status": "success",
            "deployment": "ec2_source_code",
            "public_ip": public_ip,
            "endpoint": endpoint,
            "message": f"Deployed {language} backend successfully.",
        }

    return {"status": "manual", "message": "Unknown project type."}
