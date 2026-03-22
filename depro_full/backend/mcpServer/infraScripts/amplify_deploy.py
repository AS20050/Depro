import boto3
import os
import shutil
import requests
import time
from dotenv import load_dotenv

load_dotenv()

def deploy_amplify_node_ex(source_path, app_name="opsonic-frontend"):
    """
    Deploys a local folder to AWS Amplify Console (Manual Deploy).
    Returns the public URL.
    """
    REGION = os.getenv("AWS_DEFAULT_REGION", "ap-south-1")
    amplify = boto3.client("amplify", region_name=REGION)
    
    print(f"\n🚀 [SCRIPT] Starting Amplify Deployment for: {app_name}")

    # ---------------- 1. PREPARE ZIP ----------------
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Source path not found: {source_path}")

    zip_name = "amplify_deploy_package"
    zip_file = f"{zip_name}.zip"
    
    print("📦 [SCRIPT] Zipping source code...")
    shutil.make_archive(zip_name, 'zip', source_path)
    print(f"✅ [SCRIPT] Zip created: {zip_file}")

    # ---------------- 2. CREATE/FIND APP ----------------
    # Try to find existing app by name
    apps = amplify.list_apps()
    app_id = None
    
    for app in apps['apps']:
        if app['name'] == app_name:
            app_id = app['appId']
            print(f"🔍 [SCRIPT] Found existing Amplify App ID: {app_id}")
            break
    
    if not app_id:
        print("🆕 [SCRIPT] Creating new Amplify App...")
        res = amplify.create_app(
            name=app_name,
            platform='WEB',
            environmentVariables={'_LIVE_UPDATES': '[{"pkg":"@aws-amplify/cli","type":"npm","version":"latest"}]'}
        )
        app_id = res['app']['appId']
        print(f"✅ [SCRIPT] App Created. ID: {app_id}")

    # ---------------- 3. CREATE BRANCH ----------------
    branch_name = "main"
    try:
        amplify.get_branch(appId=app_id, branchName=branch_name)
        print(f"🔍 [SCRIPT] Branch '{branch_name}' exists.")
    except amplify.exceptions.NotFoundException:
        print(f"🌿 [SCRIPT] Creating branch '{branch_name}'...")
        amplify.create_branch(appId=app_id, branchName=branch_name)

    # ---------------- 4. CREATE DEPLOYMENT ----------------
    print("☁️ [SCRIPT] Creating deployment entry...")
    deploy_config = amplify.create_deployment(appId=app_id, branchName=branch_name)
    
    job_id = deploy_config['jobId']
    upload_url = deploy_config['zipUploadUrl']
    
    # ---------------- 5. UPLOAD ZIP ----------------
    print("📤 [SCRIPT] Uploading artifact to Amplify...")
    with open(zip_file, 'rb') as f:
        # Amplify expects a PUT request with the binary data
        requests.put(upload_url, data=f)
    print("✅ [SCRIPT] Upload complete.")

    # ---------------- 6. START DEPLOYMENT ----------------
    print("🚀 [SCRIPT] Starting deployment job...")
    amplify.start_deployment(appId=app_id, branchName=branch_name, jobId=job_id)

    # ---------------- 7. WAIT FOR SUCCESS ----------------
    print("⏳ [SCRIPT] Waiting for deployment to finish (this takes ~2-3 mins)...")
    
    deploy_url = f"https://{branch_name}.{app_id}.amplifyapp.com"
    
    for _ in range(30): # Wait up to 5 minutes
        job = amplify.get_job(appId=app_id, branchName=branch_name, jobId=job_id)
        status = job['job']['summary']['status']
        print(f"   Status: {status}")
        
        if status == 'SUCCEED':
            print(f"\n✅ [SCRIPT] DEPLOYMENT SUCCESSFUL!")
            print(f"🌍 Live URL: {deploy_url}")
            # Cleanup
            if os.path.exists(zip_file): os.remove(zip_file)
            return {"status": "success", "url": deploy_url, "app_id": app_id}
            
        if status in ['FAILED', 'CANCELLED']:
            raise Exception(f"Deployment failed with status: {status}")
            
        time.sleep(10)

    raise TimeoutError("Deployment timed out, but might still be processing.")