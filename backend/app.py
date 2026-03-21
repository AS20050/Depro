import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

import os
import traceback
import shutil
import time

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from fileUploadLayer.services.zip_handler import extract_zip
from fileUploadLayer.services.github_handler import clone_github_repo
from codeReviewLayer.reviewer import review_project
from aiLayer.decision_engine import decide_and_execute
from auth.aws_credentials import ask_aws_credentials, inject_aws_creds

app = FastAPI(title="Depro")

# ==========================================
# 🔌 ENABLE CORS
# ==========================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- STORAGE ----------------
UPLOAD_DIR = Path("storage/uploads")
EXTRACT_DIR = Path("storage/extracted/zip")

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
EXTRACT_DIR.mkdir(parents=True, exist_ok=True)

# =========================================================
# 1️⃣ GENERIC UPLOAD + ORCHESTRATION
# =========================================================
@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    aws_access_key_id: str | None = Form(None),
    aws_secret_access_key: str | None = Form(None)
):
    try:
        # --- 🛡️ SANITIZE FILENAME (FIX FOR PERMISSION ERROR) ---
        original_name = file.filename
        
        # 1. Fallback if empty
        if not original_name:
            original_name = "unknown_file"

        # 2. Strip paths and whitespace (Fixes Windows "folder vs file" issue)
        clean_name = os.path.basename(original_name).strip()
        
        # 3. Ensure it's not empty after stripping
        if not clean_name:
            clean_name = f"upload_{int(time.time())}.bin"
            
        filename = clean_name
        upload_path = UPLOAD_DIR / filename
        # -------------------------------------------------------

        # Save uploaded file
        print(f"📝 Saving to: {upload_path}")
        with open(upload_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        print(f"\n📥 File uploaded: {upload_path}")

        # -------------------------------------------------
        # ZIP PATH → extract → review → AI decision
        # -------------------------------------------------
        if filename.endswith(".zip"):
            extract_path = EXTRACT_DIR
            
            if extract_path.exists():
                shutil.rmtree(extract_path)
            extract_path.mkdir(parents=True, exist_ok=True)

            extract_zip(upload_path, extract_path)
            print(f"📂 ZIP extracted to: {extract_path}")

            review_output = review_project(str(extract_path))
            
            deployment_context = review_output.copy()
            deployment_context["project_path"] = str(extract_path)
            deployment_context["filename"] = filename
            deployment_context["repo_url"] = None
            deployment_context["github_token"] = None

            return decide_and_execute(deployment_context)

        # -------------------------------------------------
        # JAR PATH → direct EC2 deployment
        # -------------------------------------------------
        if filename.endswith(".jar"):
            print("\n📦 JAR detected → direct EC2 deployment")

            # Check Frontend Creds first
            if aws_access_key_id and aws_secret_access_key:
                print("🔐 AWS Credentials received via API.")
                creds = {
                    "AWS_ACCESS_KEY_ID": aws_access_key_id,
                    "AWS_SECRET_ACCESS_KEY": aws_secret_access_key,
                    "AWS_DEFAULT_REGION": "ap-south-1" 
                }
            else:
                print("⚠️ No API credentials found. Falling back to terminal input...")
                creds = ask_aws_credentials()

            inject_aws_creds(creds)

            # SET ENV VARS FOR DEPLOY SCRIPT
            os.environ["APP_FILE"] = filename
            os.environ["APP_PORT"] = "8080"
            os.environ["KEY_NAME"] = "ubuntu-auto-keypair-v2"

            print("⚙️ Deployment env set:")
            print(f"   APP_FILE={os.environ['APP_FILE']}")

            # Copy JAR to project root
            root_jar_path = Path(filename)
            # Remove existing if present to avoid permission errors on copy
            if root_jar_path.exists():
                try:
                    os.remove(root_jar_path)
                except:
                    pass
            
            shutil.copy(upload_path, root_jar_path)
            print(f"📄 Copied JAR to project root: {root_jar_path}")

            # Trigger MCP deployment
            return decide_and_execute({
                "artifact_type": "jar",
                "artifact_path": str(upload_path)
            })

        # -------------------------------------------------
        # Unsupported file
        # -------------------------------------------------
        return {
            "status": "uploaded",
            "file": filename,
            "message": "File stored. No deployment pipeline for this file type yet."
        }

    except Exception as e:
        print("---------------- ERROR TRACEBACK ----------------")
        traceback.print_exc()
        print("------------------------------------------------")
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================
# 2️⃣ STANDALONE REVIEW ENDPOINT
# =========================================================
class ReviewRequest(BaseModel):
    project_path: str

@app.post("/review")
async def review_repo(request: ReviewRequest):
    try:
        print(f"\n🔍 Starting review for: {request.project_path}")
        result = review_project(request.project_path)
        return {
            "status": "success",
            "review": result
        }
    except Exception as e:
        print("---------------- ERROR TRACEBACK ----------------")
        traceback.print_exc()
        print("------------------------------------------------")
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================
# 3️⃣ GITHUB UPLOAD
# =========================================================
@app.post("/upload/github")
async def upload_github_repo(
    repo_url: str = Form(...),
    github_token: str | None = Form(None)
):
    try:
        # 1. Clone
        repo_path = clone_github_repo(repo_url, github_token)
        print(f"\n📦 GitHub repo cloned to: {repo_path}")

        # 2. Review
        review_output = review_project(repo_path)
        
        # 3. Context Injection
        deployment_context = review_output.copy()
        deployment_context["project_path"] = repo_path
        deployment_context["filename"] = repo_url.split("/")[-1] 
        deployment_context["repo_url"] = repo_url
        deployment_context["github_token"] = github_token

        # 4. Execute
        return decide_and_execute(deployment_context)

    except Exception as e:
        print("---------------- ERROR TRACEBACK ----------------")
        traceback.print_exc()
        print("------------------------------------------------")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)