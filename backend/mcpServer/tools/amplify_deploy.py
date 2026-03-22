import boto3
import os
import shutil
import requests
import time
import subprocess
import json
from dotenv import load_dotenv

load_dotenv()

def deploy_amplify_node_ex(source_path, app_name="depro-frontend"):
    """
    Builds a React/Vite app and deploys the 'dist' folder to AWS Amplify.
    """
    REGION = os.getenv("AWS_DEFAULT_REGION", "ap-south-1")
    amplify = boto3.client("amplify", region_name=REGION)
    
    print(f"\n🚀 [SCRIPT] Starting Smart Amplify Deployment for: {app_name}")

    # ---------------- 1. DETECT & BUILD ----------------
    if not os.path.exists(os.path.join(source_path, "package.json")):
        raise FileNotFoundError("❌ No package.json found! Cannot build frontend.")

    print("🔨 [SCRIPT] Detected Node.js project. Installing dependencies...")
    # Use shell=True for Windows compatibility
    subprocess.run("npm install", shell=True, check=True, cwd=source_path)

    print("🔨 [SCRIPT] Building project for production...")
    subprocess.run("npm run build", shell=True, check=True, cwd=source_path)

    # Detect build output folder (Vite uses 'dist', Create-React-App uses 'build')
    build_dir = os.path.join(source_path, "dist")
    if not os.path.exists(build_dir):
        build_dir = os.path.join(source_path, "build")
    
    if not os.path.exists(build_dir):
        raise FileNotFoundError("❌ Build failed. Could not find 'dist' or 'build' directory.")

    print(f"✅ [SCRIPT] Build successful! Output directory: {build_dir}")

    # ---------------- 2. ZIP BUILD OUTPUT ----------------
    # We zip the *contents* of dist, not the dist folder itself
    zip_name = "amplify_build_artifact"
    zip_file = f"{zip_name}.zip"
    
    print("📦 [SCRIPT] Zipping build artifacts...")
    shutil.make_archive(zip_name, 'zip', build_dir)
    print(f"✅ [SCRIPT] Zip created: {zip_file}")

    # ---------------- 3. CREATE/FIND APP ----------------
    # For snapshot (ZIP) deploys, we need an app that is NOT connected to a repo.
    # If the existing app is repo-connected, create a new one with '-snapshot' suffix.
    apps = amplify.list_apps()
    app_id = None
    
    for app in apps['apps']:
        if app['name'] == app_name:
            # Check if this app is repo-connected
            repo = app.get('repository')
            if repo:
                print(f"⚠️ [SCRIPT] App '{app_name}' is connected to a repo. Creating snapshot app...")
                app_id = None  # Force new app creation
                app_name = f"{app_name}-snapshot"
                # Check if snapshot app already exists
                for a2 in apps['apps']:
                    if a2['name'] == app_name and not a2.get('repository'):
                        app_id = a2['appId']
                        print(f"🔍 [SCRIPT] Found existing snapshot App ID: {app_id}")
                        break
            else:
                app_id = app['appId']
                print(f"🔍 [SCRIPT] Found existing Amplify App ID: {app_id}")
            break
    
    if not app_id:
        print(f"🆕 [SCRIPT] Creating new Amplify App: {app_name}")
        res = amplify.create_app(name=app_name, platform='WEB')
        app_id = res['app']['appId']
        print(f"✅ [SCRIPT] App Created. ID: {app_id}")

    # ---------------- 4. DEPLOY TO BRANCH ----------------
    branch_name = "main"
    try:
        amplify.get_branch(appId=app_id, branchName=branch_name)
    except amplify.exceptions.NotFoundException:
        print(f"🌿 [SCRIPT] Creating branch '{branch_name}'...")
        amplify.create_branch(appId=app_id, branchName=branch_name)

    print("☁️ [SCRIPT] Creating deployment entry...")
    deploy_config = amplify.create_deployment(appId=app_id, branchName=branch_name)
    job_id = deploy_config['jobId']
    upload_url = deploy_config['zipUploadUrl']
    
    print("📤 [SCRIPT] Uploading build artifacts to Amplify...")
    with open(zip_file, 'rb') as f:
        requests.put(upload_url, data=f)
    print("✅ [SCRIPT] Upload complete.")

    print("🚀 [SCRIPT] Starting deployment job...")
    amplify.start_deployment(appId=app_id, branchName=branch_name, jobId=job_id)

    # ---------------- 5. VERIFY ----------------
    print("⏳ [SCRIPT] Waiting for deployment to go live...")
    deploy_url = f"https://{branch_name}.{app_id}.amplifyapp.com"
    
    for _ in range(30):
        job = amplify.get_job(appId=app_id, branchName=branch_name, jobId=job_id)
        status = job['job']['summary']['status']
        print(f"   Status: {status}")
        
        if status == 'SUCCEED':
            print(f"\n✅ [SCRIPT] WEBSITE IS LIVE!")
            print(f"🌍 URL: {deploy_url}")
            if os.path.exists(zip_file): os.remove(zip_file)
            return {"status": "success", "url": deploy_url, "app_id": app_id}
            
        if status in ['FAILED', 'CANCELLED']:
            raise Exception(f"Deployment failed: {status}")
        time.sleep(5)

    raise TimeoutError("Deployment timed out.")