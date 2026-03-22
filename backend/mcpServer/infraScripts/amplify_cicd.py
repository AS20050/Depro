import boto3
import os
import time
import requests
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()

def connect_amplify_repo_ex(repo_url, github_token, app_name="opsonic-cicd-app"):
    """
    Connects AWS Amplify directly to a GitHub Repository.
    Fixes: React 19/Vite 7/Tailwind 4 support by forcing Amazon Linux 2023.
    """
    REGION = os.getenv("AWS_DEFAULT_REGION", "ap-south-1")
    amplify = boto3.client("amplify", region_name=REGION)

    print(f"\n🚀 [SCRIPT] Connecting Amplify CI/CD for: {repo_url}")

    if not repo_url.startswith("https://"):
        repo_url = f"https://{repo_url}"

    # ---------------------------------------------------------
    # 0. DEFINE BUILD SPEC (Node 20 + Dist)
    # ---------------------------------------------------------
    vite_build_spec = """version: 1
frontend:
  phases:
    preBuild:
      commands:
        - echo "🔍 Checking Node version..."
        - nvm install 20
        - nvm use 20
        - node -v
        - npm -v
        - echo "📦 Installing dependencies..."
        - npm ci --legacy-peer-deps || npm install --legacy-peer-deps
        - echo "✅ Dependencies installed"
    build:
      commands:
        - echo "🏗️ Building application..."
        - npm run build
        - echo "📂 Build output directory:"
        - ls -la
        - ls -la dist 2>/dev/null || ls -la build 2>/dev/null || echo "No dist/build folder found"
  artifacts:
    baseDirectory: dist
    files:
      - '**/*'
  cache:
    paths:
      - node_modules/**/*
"""

    # ---------------------------------------------------------
    # 1. CREATE APP (With Amazon Linux 2023 Fix)
    # ---------------------------------------------------------
    app_id = None
    try:
        print("🔗 [SCRIPT] Linking AWS to GitHub (Configuring AL2023 Image)...")
        res = amplify.create_app(
            name=app_name,
            repository=repo_url,
            accessToken=github_token,
            platform='WEB',
            enableAutoBranchCreation=True,
            buildSpec=vite_build_spec,
            # 🔥 CRITICAL FIXES FOR REACT 19 / TAILWIND 4
            environmentVariables={
                'AMPLIFY_MONOREPO_APP_ROOT': '/',
                '_CUSTOM_IMAGE': 'amplify:al2023',
                'CI': 'false',
                'NODE_OPTIONS': '--max-old-space-size=4096',
                # Additional compatibility settings
                'AMPLIFY_DIFF_DEPLOY': 'false',
                'AMPLIFY_SKIP_BACKEND_BUILD': 'true'
            } 
        )
        app_id = res['app']['appId']
        print(f"✅ [SCRIPT] App Linked. ID: {app_id}")

    except ClientError as e:
        error_code = e.response['Error']['Code']
        if "BadRequestException" in error_code and "already exists" in str(e):
             raise Exception(f"❌ App '{app_name}' already exists. Please delete it in AWS Console and retry.")
        else:
             raise e

    # ---------------------------------------------------------
    # 2. DETECT & CREATE DEFAULT BRANCH
    # ---------------------------------------------------------
    branch_name = _get_default_branch(repo_url, github_token)
    print(f"🌿 [SCRIPT] Using branch '{branch_name}'...")
    
    try:
        amplify.get_branch(appId=app_id, branchName=branch_name)
        print(f"   ✅ Branch '{branch_name}' already connected.")
    except ClientError as e:
        if "NotFoundException" in str(e) or "ResourceNotFoundException" in str(e):
            # Branch doesn't exist in Amplify, try to create it
            try:
                print(f"   🔄 Attempting to connect branch '{branch_name}'...")
                amplify.create_branch(appId=app_id, branchName=branch_name)
                print(f"   ✨ Branch '{branch_name}' connected successfully.")
            except ClientError as create_err:
                error_msg = str(create_err)
                if "not found" in error_msg.lower() or "does not exist" in error_msg.lower():
                    # Branch doesn't exist in GitHub repo - try alternatives
                    print(f"   ❌ Branch '{branch_name}' not found in repository.")
                    alternative_branches = ['master', 'master', 'develop']
                    
                    for alt_branch in alternative_branches:
                        if alt_branch != branch_name:
                            try:
                                print(f"   🔄 Trying alternative branch: '{alt_branch}'...")
                                amplify.create_branch(appId=app_id, branchName=alt_branch)
                                branch_name = alt_branch
                                print(f"   ✨ Successfully connected to '{alt_branch}'.")
                                break
                            except:
                                continue
                    else:
                        raise Exception(f"❌ Could not find any valid branch (tried: {', '.join([branch_name] + alternative_branches)}). Please check your GitHub repository.")
                else:
                    raise Exception(f"❌ Failed to create branch: {create_err}")
        else:
            raise e

    # ---------------------------------------------------------
    # 3. TRIGGER & WAIT FOR BUILD
    # ---------------------------------------------------------
    print("🚀 [SCRIPT] Triggering initial build...")
    job_id = None
    try:
        job_res = amplify.start_job(appId=app_id, branchName=branch_name, jobType='RELEASE')
        job_id = job_res['jobSummary']['jobId']
        print(f"   ⏳ Build Job Started: {job_id}")
    except Exception as e:
        print(f"   ⚠️ Could not trigger job: {e}")

    print("   ⏳ Waiting for deployment to complete (this takes 2-3 mins)...")
    live_url = f"https://{branch_name}.{app_id}.amplifyapp.com"
    
    # Tracking Loop with Enhanced Error Capture
    last_status = None
    for iteration in range(60): 
        try:
            if job_id:
                job_data = amplify.get_job(appId=app_id, branchName=branch_name, jobId=job_id)
                status = job_data['job']['summary']['status']
                
                # Only print if status changed
                if status != last_status:
                    print(f"      ... Status: {status}")
                    last_status = status
            else:
                status = "RUNNING"
                print(f"      ... Status: {status}")

            if status in ['SUCCEEDED', 'SUCCEED']:
                print(f"\n✅ [SCRIPT] Deployment Complete!")
                print(f"🌐 Live URL: {live_url}")
                break
                
            elif status in ['FAILED', 'CANCELLED']:
                console_url = f"https://{REGION}.console.aws.amazon.com/amplify/home?region={REGION}#/{app_id}/{branch_name}/{job_id}"
                
                # Try to get detailed error information
                error_details = _get_build_error_details(amplify, app_id, branch_name, job_id)
                
                print(f"\n❌ Deployment {status}")
                print(f"📋 View Full Logs: {console_url}")
                
                if error_details:
                    print(f"\n🔍 Error Details:")
                    print(error_details)
                
                raise Exception(f"Deployment {status}. Check AWS Console for detailed logs: {console_url}")
            
            time.sleep(5)
            
        except Exception as e:
            if "Deployment" in str(e) and ("FAILED" in str(e) or "CANCELLED" in str(e)):
                raise e
            print(f"   ⚠️ Tracking interrupted: {e}")
            break
    else:
        # Timeout reached - but deployment might still have succeeded
        console_url = f"https://{REGION}.console.aws.amazon.com/amplify/home?region={REGION}#/{app_id}/{branch_name}/{job_id if job_id else ''}"
        print(f"\n⏱️ Status check timeout reached (5 minutes)")
        
        # Do one final check
        try:
            if job_id:
                final_check = amplify.get_job(appId=app_id, branchName=branch_name, jobId=job_id)
                final_status = final_check['job']['summary']['status']
                if final_status in ['SUCCEEDED', 'SUCCEED']:
                    print(f"✅ [SCRIPT] Deployment completed successfully!")
                    print(f"🌐 Live URL: {live_url}")
                else:
                    print(f"📋 Final Status: {final_status}")
                    print(f"📋 Check console: {console_url}")
        except:
            print(f"📋 Check deployment status: {console_url}")
            print(f"🌐 If deployment succeeded, your app is at: {live_url}")

    return {
        "status": "success",
        "url": live_url,
        "app_id": app_id,
        "branch_name": branch_name,
        "job_id": job_id,
        "console_url": f"https://{REGION}.console.aws.amazon.com/amplify/home?region={REGION}#/{app_id}",
        "mode": "cicd",
        "message": f"Your app is live at: {live_url}"
    }


def _get_default_branch(repo_url, github_token):
    """
    Detects the default branch of a GitHub repository.
    Returns 'master', 'master', or the actual default branch name.
    """
    import requests
    
    # Extract owner and repo from URL
    # Format: https://github.com/owner/repo or https://github.com/owner/repo.git
    parts = repo_url.rstrip('/').rstrip('.git').split('/')
    if len(parts) >= 2:
        owner = parts[-2]
        repo = parts[-1]
    else:
        print("   ⚠️ Could not parse repo URL, defaulting to 'master'")
        return 'master'
    
    try:
        # Use GitHub API to get repository info
        api_url = f"https://api.github.com/repos/{owner}/{repo}"
        headers = {
            'Authorization': f'token {github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        response = requests.get(api_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            default_branch = data.get('default_branch', 'master')
            print(f"   ✅ Detected default branch: '{default_branch}'")
            return default_branch
        else:
            print(f"   ⚠️ GitHub API returned {response.status_code}, trying common branches...")
            
    except Exception as e:
        print(f"   ⚠️ Error detecting branch: {e}, trying common branches...")
    
    # Fallback: try common branch names
    return 'master'  # Will be validated in the next step


def _get_build_error_details(amplify, app_id, branch_name, job_id):
    """
    Attempts to retrieve detailed error information from Amplify build logs.
    """
    try:
        job_data = amplify.get_job(appId=app_id, branchName=branch_name, jobId=job_id)
        
        # Extract steps and find failed ones
        steps = job_data.get('job', {}).get('steps', [])
        errors = []
        
        for step in steps:
            if step.get('status') == 'FAILED':
                step_name = step.get('stepName', 'Unknown')
                log_url = step.get('logUrl', '')
                errors.append(f"  ❌ Failed at: {step_name}")
                if log_url:
                    errors.append(f"     Log: {log_url}")
        
        if errors:
            return "\n".join(errors)
        
        # If no specific step errors, return generic message
        return "  No detailed error information available. Check AWS Console logs."
        
    except Exception as e:
        return f"  Could not retrieve error details: {str(e)}"