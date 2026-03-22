# import sys
# from pathlib import Path
# sys.path.append(str(Path(__file__).parent))

# from dotenv import load_dotenv
# load_dotenv()
# from billing_routes import router as billing_router
# import os
# import traceback
# import shutil
# import time
# from contextlib import asynccontextmanager
# from typing import Optional

# from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Header
# from fastapi.middleware.cors import CORSMiddleware
# from pydantic import BaseModel
# from jose import jwt, JWTError

# from fileUploadLayer.services.zip_handler import extract_zip
# from fileUploadLayer.services.github_handler import clone_github_repo
# from codeReviewLayer.reviewer import review_project
# from aiLayer.decision_engine import decide_and_execute
# from auth.aws_credentials import ask_aws_credentials, inject_aws_creds
# from auth.routes import router as auth_router
# from auth.github_oauth import router as github_oauth_router
# from db.database import init_db
# from endpoints.dashboard import router as dashboard_router
# from endpoints.deployments import router as deployments_router
# from endpoints.aws_accounts import router as aws_accounts_router
# from endpoints.deployment_service import record_deployment

# JWT_SECRET = os.getenv("JWT_SECRET", "depro-fallback-secret")


# def _extract_user_id(authorization: Optional[str]) -> Optional[str]:
#     """Try to extract user_id from Bearer token. Returns None if invalid/missing."""
#     if not authorization or not authorization.startswith("Bearer "):
#         return None
#     try:
#         token = authorization.split(" ")[1]
#         payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
#         return payload.get("sub")
#     except (JWTError, Exception):
#         return None


# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     """Initialize database on startup."""
#     await init_db()
#     yield

# app = FastAPI(title="DePro", lifespan=lifespan)

# # Register auth routers
# app.include_router(auth_router)
# app.include_router(github_oauth_router)

# # Register API endpoint routers
# app.include_router(dashboard_router)
# app.include_router(deployments_router)
# app.include_router(aws_accounts_router)

# # ==========================================
# # 🔌 ENABLE CORS
# # ==========================================
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )
# app.include_router(billing_router, prefix="/billing", tags=["Billing"])
# # ---------------- STORAGE ----------------
# UPLOAD_DIR = Path("storage/uploads")
# EXTRACT_DIR = Path("storage/extracted/zip")

# UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
# EXTRACT_DIR.mkdir(parents=True, exist_ok=True)

# # =========================================================
# # 1️⃣ GENERIC UPLOAD + ORCHESTRATION
# # =========================================================
# @app.post("/upload")
# async def upload_file(
#     file: UploadFile = File(...),
#     aws_access_key_id: str | None = Form(None),
#     aws_secret_access_key: str | None = Form(None),
#     authorization: Optional[str] = Header(None)
# ):
#     user_id = _extract_user_id(authorization)
#     try:
#         # --- 🛡️ SANITIZE FILENAME ---
#         original_name = file.filename
#         if not original_name:
#             original_name = "unknown_file"
#         clean_name = os.path.basename(original_name).strip()
#         if not clean_name:
#             clean_name = f"upload_{int(time.time())}.bin"
#         filename = clean_name
#         upload_path = UPLOAD_DIR / filename

#         # Save uploaded file
#         print(f"📝 Saving to: {upload_path}")
#         with open(upload_path, "wb") as f:
#             shutil.copyfileobj(file.file, f)
#         print(f"\n📥 File uploaded: {upload_path}")

#         # -------------------------------------------------
#         # ZIP PATH → extract → review → AI decision
#         # -------------------------------------------------
#         if filename.endswith(".zip"):
#             extract_path = EXTRACT_DIR
#             if extract_path.exists():
#                 shutil.rmtree(extract_path)
#             extract_path.mkdir(parents=True, exist_ok=True)
#             extract_zip(upload_path, extract_path)
#             print(f"📂 ZIP extracted to: {extract_path}")

#             review_output = review_project(str(extract_path))
#             deployment_context = review_output.copy()
#             deployment_context["project_path"] = str(extract_path)
#             deployment_context["filename"] = filename
#             deployment_context["repo_url"] = None
#             deployment_context["github_token"] = None

#             result = decide_and_execute(deployment_context)

#             # 📝 Record to DB
#             if user_id:
#                 dep_status = "success" if result.get("status") == "success" or result.get("endpoint") else "failed"
#                 await record_deployment(
#                     user_id=user_id,
#                     source_type="zip",
#                     source_filename=filename,
#                     file_path=str(upload_path),
#                     project_type=result.get("project_type") or review_output.get("type"),
#                     deployment_type=result.get("deployment"),
#                     status=dep_status,
#                     endpoint=result.get("endpoint") or result.get("url") or (result.get("details", {}) or {}).get("url"),
#                     app_id=result.get("app_id"),
#                     aws_service=result.get("deployment", "amplify").split("_")[0] if result.get("deployment") else "amplify",
#                     error_message=result.get("error")
#                 )
#             return result

#         # -------------------------------------------------
#         # JAR PATH → direct EC2 deployment
#         # -------------------------------------------------
#         if filename.endswith(".jar"):
#             print("\n📦 JAR detected → direct EC2 deployment")
#             if aws_access_key_id and aws_secret_access_key:
#                 print("🔐 AWS Credentials received via API.")
#                 creds = {
#                     "AWS_ACCESS_KEY_ID": aws_access_key_id,
#                     "AWS_SECRET_ACCESS_KEY": aws_secret_access_key,
#                     "AWS_DEFAULT_REGION": "ap-south-1"
#                 }
#             else:
#                 print("⚠️ No API credentials found. Falling back to terminal input...")
#                 creds = ask_aws_credentials()
#             inject_aws_creds(creds)

#             os.environ["APP_FILE"] = filename
#             os.environ["APP_PORT"] = "8080"
#             os.environ["KEY_NAME"] = "ubuntu-auto-keypair-v2"

#             root_jar_path = Path(filename)
#             if root_jar_path.exists():
#                 try:
#                     os.remove(root_jar_path)
#                 except:
#                     pass
#             shutil.copy(upload_path, root_jar_path)

#             result = decide_and_execute({
#                 "artifact_type": "jar",
#                 "artifact_path": str(upload_path)
#             })

#             # 📝 Record to DB
#             if user_id:
#                 dep_status = "success" if result.get("status") == "success" or result.get("endpoint") else "failed"
#                 await record_deployment(
#                     user_id=user_id,
#                     source_type="jar",
#                     source_filename=filename,
#                     file_path=str(upload_path),
#                     project_type="backend",
#                     deployment_type="ec2",
#                     status=dep_status,
#                     endpoint=result.get("endpoint") or result.get("url"),
#                     aws_service="ec2",
#                     error_message=result.get("error")
#                 )
#             return result

#         return {
#             "status": "uploaded",
#             "file": filename,
#             "message": "File stored. No deployment pipeline for this file type yet."
#         }

#     except Exception as e:
#         print("---------------- ERROR TRACEBACK ----------------")
#         traceback.print_exc()
#         print("------------------------------------------------")
#         # Record failure
#         if user_id:
#             try:
#                 await record_deployment(
#                     user_id=user_id,
#                     source_type="zip" if file.filename and file.filename.endswith(".zip") else "jar",
#                     source_filename=file.filename,
#                     status="failed",
#                     error_message=str(e)
#                 )
#             except:
#                 pass
#         raise HTTPException(status_code=500, detail=str(e))


# # =========================================================
# # 2️⃣ STANDALONE REVIEW ENDPOINT
# # =========================================================
# class ReviewRequest(BaseModel):
#     project_path: str

# @app.post("/review")
# async def review_repo(request: ReviewRequest):
#     try:
#         print(f"\n🔍 Starting review for: {request.project_path}")
#         result = review_project(request.project_path)
#         return {"status": "success", "review": result}
#     except Exception as e:
#         print("---------------- ERROR TRACEBACK ----------------")
#         traceback.print_exc()
#         print("------------------------------------------------")
#         raise HTTPException(status_code=500, detail=str(e))


# # =========================================================
# # 3️⃣ GITHUB UPLOAD
# # =========================================================
# @app.post("/upload/github")
# async def upload_github_repo(
#     repo_url: str = Form(...),
#     github_token: str | None = Form(None),
#     authorization: Optional[str] = Header(None)
# ):
#     user_id = _extract_user_id(authorization)
#     try:
#         repo_path = clone_github_repo(repo_url, github_token)
#         print(f"\n📦 GitHub repo cloned to: {repo_path}")

#         review_output = review_project(repo_path)
#         deployment_context = review_output.copy()
#         deployment_context["project_path"] = repo_path
#         deployment_context["filename"] = repo_url.split("/")[-1]
#         deployment_context["repo_url"] = repo_url
#         deployment_context["github_token"] = github_token

#         result = decide_and_execute(deployment_context)

#         # 📝 Record to DB
#         if user_id:
#             dep_status = "success" if result.get("status") == "success" or result.get("endpoint") else "failed"
#             await record_deployment(
#                 user_id=user_id,
#                 source_type="github",
#                 source_filename=repo_url.split("/")[-1],
#                 repo_url=repo_url,
#                 project_type=result.get("project_type") or review_output.get("type"),
#                 deployment_type=result.get("deployment"),
#                 status=dep_status,
#                 endpoint=result.get("endpoint") or result.get("url") or (result.get("details", {}) or {}).get("url"),
#                 app_id=result.get("app_id"),
#                 aws_service=result.get("deployment", "amplify").split("_")[0] if result.get("deployment") else "amplify",
#                 error_message=result.get("error")
#             )
#         return result

#     except Exception as e:
#         print("---------------- ERROR TRACEBACK ----------------")
#         traceback.print_exc()
#         print("------------------------------------------------")
#         if user_id:
#             try:
#                 await record_deployment(
#                     user_id=user_id,
#                     source_type="github",
#                     repo_url=repo_url,
#                     status="failed",
#                     error_message=str(e)
#                 )
#             except:
#                 pass
#         raise HTTPException(status_code=500, detail=str(e))


# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).parent / ".env")  # explicit path fixes .env not loading

import os
import traceback
import shutil
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from jose import jwt, JWTError

from fileUploadLayer.services.zip_handler import extract_zip
from fileUploadLayer.services.github_handler import clone_github_repo
from codeReviewLayer.reviewer import review_project
from aiLayer.decision_engine import decide_and_execute
from auth.aws_credentials import ask_aws_credentials, inject_aws_creds
from auth.routes import router as auth_router
from auth.github_oauth import router as github_oauth_router
from db.database import init_db
from endpoints.dashboard import router as dashboard_router
from endpoints.deployments import router as deployments_router
from endpoints.aws_accounts import router as aws_accounts_router
from endpoints.deployment_service import record_deployment
from billing_routes import router as billing_router
from endpoints.vault import router as vault_router

JWT_SECRET = os.getenv("JWT_SECRET", "depro-fallback-secret")


def _extract_user_id(authorization: Optional[str]) -> Optional[str]:
    """Try to extract user_id from Bearer token. Returns None if invalid/missing."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    try:
        token   = authorization.split(" ")[1]
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload.get("sub")
    except (JWTError, Exception):
        return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    await init_db()
    yield


app = FastAPI(title="DePro", lifespan=lifespan)

# ==========================================
# CORS — added FIRST before all routers
# ==========================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# ALL ROUTERS
# ==========================================
app.include_router(auth_router)
app.include_router(github_oauth_router)
app.include_router(dashboard_router)
app.include_router(deployments_router)
app.include_router(aws_accounts_router)
app.include_router(billing_router, prefix="/billing", tags=["Billing"])
app.include_router(vault_router)

# ---------------- STORAGE ----------------
UPLOAD_DIR  = Path("storage/uploads")
EXTRACT_DIR = Path("storage/extracted/zip")

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
EXTRACT_DIR.mkdir(parents=True, exist_ok=True)


# =========================================================
# CREDENTIAL RESOLUTION HELPERS
# =========================================================
async def _resolve_aws_creds(
    user_id: str | None,
    form_key: str | None = None,
    form_secret: str | None = None,
    form_region: str | None = None,
) -> dict | None:
    """
    Try to resolve AWS credentials in order:
    1. Form-submitted creds (user just provided them)
    2. Algorand vault (user previously stored them)
    Returns None if no credentials are available anywhere.
    """
    # 1. Form submission (user explicitly sent creds)
    if form_key and form_secret:
        print("🔐 AWS Credentials received via form.")
        return {
            "AWS_ACCESS_KEY_ID":     form_key.strip(),
            "AWS_SECRET_ACCESS_KEY": form_secret.strip(),
            "AWS_DEFAULT_REGION":    (form_region or "ap-south-1").strip(),
        }

    # 2. Algorand vault lookup
    if user_id:
        try:
            from sqlalchemy import select
            from db.database import async_session
            from db.models import User as UserModel
            async with async_session() as sess:
                result = await sess.execute(
                    select(UserModel.aws_access_key_id).where(UserModel.id == user_id)
                )
                stored_key = result.scalar_one_or_none()
                if stored_key:
                    from credential_vault import vault_retrieve
                    vault_data = vault_retrieve(stored_key)
                    print(f"🔐 AWS Credentials retrieved from Algorand vault ({stored_key[:8]}****)")
                    return {
                        "AWS_ACCESS_KEY_ID":     vault_data["AWS_ACCESS_KEY_ID"],
                        "AWS_SECRET_ACCESS_KEY": vault_data["AWS_SECRET_ACCESS_KEY"],
                        "AWS_DEFAULT_REGION":    vault_data.get("AWS_DEFAULT_REGION", "ap-south-1"),
                    }
        except Exception as ve:
            print(f"⚠️ Vault retrieval failed: {ve}")

    return None


async def _store_creds_to_vault(user_id: str, creds: dict):
    """
    Store IAM credentials to Algorand vault and save access_key_id in user's DB record.
    Called once on first-time credential submission.
    """
    try:
        from credential_vault import vault_store
        from sqlalchemy import select
        from db.database import async_session
        from db.models import User as UserModel

        access_key = creds["AWS_ACCESS_KEY_ID"]
        vault_store(
            access_key_id=access_key,
            secret_access_key=creds["AWS_SECRET_ACCESS_KEY"],
            region=creds.get("AWS_DEFAULT_REGION", "ap-south-1"),
        )

        async with async_session() as sess:
            result = await sess.execute(select(UserModel).where(UserModel.id == user_id))
            user = result.scalar_one_or_none()
            if user:
                user.aws_access_key_id = access_key
                user.aws_default_region = creds.get("AWS_DEFAULT_REGION", "ap-south-1")
                await sess.commit()
        print(f"🔐 [VAULT] Credentials stored for user {user_id}")
    except Exception as e:
        print(f"⚠️ [VAULT] Failed to store credentials: {e}")


async def _store_github_token(user_id: str, github_token: str):
    """Save GitHub PAT in user's DB record."""
    try:
        from sqlalchemy import select
        from db.database import async_session
        from db.models import User as UserModel

        async with async_session() as sess:
            result = await sess.execute(select(UserModel).where(UserModel.id == user_id))
            user = result.scalar_one_or_none()
            if user:
                user.github_token = github_token
                await sess.commit()
        print(f"🔑 [DB] GitHub PAT stored for user {user_id}")
    except Exception as e:
        print(f"⚠️ [DB] Failed to store GitHub token: {e}")


async def _get_stored_github_token(user_id: str) -> str | None:
    """Get previously stored GitHub PAT from DB."""
    try:
        from sqlalchemy import select
        from db.database import async_session
        from db.models import User as UserModel

        async with async_session() as sess:
            result = await sess.execute(
                select(UserModel.github_token).where(UserModel.id == user_id)
            )
            return result.scalar_one_or_none()
    except Exception:
        return None


# =========================================================
# 1️⃣ GENERIC UPLOAD + ORCHESTRATION
# =========================================================
@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    aws_access_key_id: str | None = Form(None),
    aws_secret_access_key: str | None = Form(None),
    aws_default_region: str | None = Form(None),
    authorization: Optional[str] = Header(None)
):
    user_id = _extract_user_id(authorization)
    try:
        original_name = file.filename
        if not original_name:
            original_name = "unknown_file"
        clean_name = os.path.basename(original_name).strip()
        if not clean_name:
            clean_name = f"upload_{int(time.time())}.bin"

        filename    = clean_name
        upload_path = UPLOAD_DIR / filename

        print(f"📝 Saving to: {upload_path}")
        with open(upload_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        print(f"\n📥 File uploaded: {upload_path}")

        # -------------------------------------------------
        # ZIP → extract → review → AI decision
        # -------------------------------------------------
        if filename.endswith(".zip"):
            extract_path = EXTRACT_DIR
            if extract_path.exists():
                shutil.rmtree(extract_path)
            extract_path.mkdir(parents=True, exist_ok=True)
            extract_zip(upload_path, extract_path)

            # ZIPs often have a single root folder (e.g. "project-master/")
            children = list(extract_path.iterdir())
            if len(children) == 1 and children[0].is_dir():
                extract_path = children[0]
                print(f"📂 ZIP extracted to nested folder, using: {extract_path}")
            else:
                print(f"📂 ZIP extracted to: {extract_path}")

            review_output      = review_project(str(extract_path))
            deployment_context = review_output.copy()
            deployment_context["project_path"] = str(extract_path)
            deployment_context["filename"]     = filename
            deployment_context["repo_url"]     = None
            deployment_context["github_token"] = None

            result = decide_and_execute(deployment_context)

            if user_id:
                dep_status = "success" if result.get("status") == "success" or result.get("endpoint") else "failed"
                await record_deployment(
                    user_id=user_id,
                    source_type="zip",
                    source_filename=filename,
                    file_path=str(upload_path),
                    project_type=result.get("project_type") or review_output.get("type"),
                    deployment_type=result.get("deployment"),
                    status=dep_status,
                    endpoint=result.get("endpoint") or result.get("url") or (result.get("details", {}) or {}).get("url"),
                    app_id=result.get("app_id"),
                    aws_service=result.get("deployment", "amplify").split("_")[0] if result.get("deployment") else "amplify",
                    error_message=result.get("error")
                )
            return result

        # -------------------------------------------------
        # JAR → needs AWS creds → vault check → deploy
        # -------------------------------------------------
        if filename.endswith(".jar"):
            print("\n📦 JAR detected → direct EC2 deployment")

            # Resolve creds: form > vault > needs_credentials
            creds = await _resolve_aws_creds(
                user_id, aws_access_key_id, aws_secret_access_key, aws_default_region
            )

            if not creds:
                return {
                    "status": "needs_credentials",
                    "needs": ["aws_iam"],
                    "message": "AWS IAM credentials required. This is a one-time setup — they will be securely stored in Algorand vault.",
                    "filename": filename,
                }

            # First-time: store in vault for next time
            if aws_access_key_id and aws_secret_access_key and user_id:
                await _store_creds_to_vault(user_id, creds)

            inject_aws_creds(creds)

            os.environ["APP_FILE"] = filename
            os.environ["APP_PORT"] = "8080"
            os.environ["KEY_NAME"] = "ubuntu-auto-keypair-v2"

            root_jar_path = Path(filename)
            if root_jar_path.exists():
                try:
                    os.remove(root_jar_path)
                except Exception:
                    pass
            shutil.copy(upload_path, root_jar_path)

            result = decide_and_execute({
                "artifact_type": "jar",
                "artifact_path": str(upload_path)
            })

            if user_id:
                dep_status = "success" if result.get("status") == "success" or result.get("endpoint") else "failed"
                await record_deployment(
                    user_id=user_id,
                    source_type="jar",
                    source_filename=filename,
                    file_path=str(upload_path),
                    project_type="backend",
                    deployment_type="ec2",
                    status=dep_status,
                    endpoint=result.get("endpoint") or result.get("url"),
                    aws_service="ec2",
                    error_message=result.get("error")
                )
            return result

        return {
            "status":  "uploaded",
            "file":    filename,
            "message": "File stored. No deployment pipeline for this file type yet."
        }

    except Exception as e:
        print("---------------- ERROR TRACEBACK ----------------")
        traceback.print_exc()
        print("------------------------------------------------")
        if user_id:
            try:
                await record_deployment(
                    user_id=user_id,
                    source_type="zip" if file.filename and file.filename.endswith(".zip") else "jar",
                    source_filename=file.filename,
                    status="failed",
                    error_message=str(e)
                )
            except Exception:
                pass
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
        return {"status": "success", "review": result}
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
    repo_url:              str          = Form(...),
    github_token:          str | None   = Form(None),
    aws_access_key_id:     str | None   = Form(None),
    aws_secret_access_key: str | None   = Form(None),
    aws_default_region:    str | None   = Form(None),
    authorization:         Optional[str] = Header(None)
):
    user_id = _extract_user_id(authorization)
    try:
        # --- Resolve GitHub PAT: form > DB > needs_credentials ---
        resolved_gh_token = github_token
        if not resolved_gh_token and user_id:
            resolved_gh_token = await _get_stored_github_token(user_id)
            if resolved_gh_token:
                print("🔑 GitHub PAT retrieved from DB.")

        # --- Resolve AWS creds: form > vault > needs_credentials ---
        creds = await _resolve_aws_creds(
            user_id, aws_access_key_id, aws_secret_access_key, aws_default_region
        )

        if not creds:
            needs = ["aws_iam"]
            if not resolved_gh_token:
                needs.append("github_token")
            return {
                "status": "needs_credentials",
                "needs": needs,
                "message": "Credentials required. This is a one-time setup — IAM keys are stored in Algorand vault.",
                "repo_url": repo_url,
            }

        # First time: store creds for next time
        if user_id:
            if aws_access_key_id and aws_secret_access_key:
                await _store_creds_to_vault(user_id, creds)
            if github_token:
                await _store_github_token(user_id, github_token)

        inject_aws_creds(creds)

        repo_path = clone_github_repo(repo_url, resolved_gh_token)
        print(f"\n📦 GitHub repo cloned to: {repo_path}")

        review_output      = review_project(repo_path)
        deployment_context = review_output.copy()
        deployment_context["project_path"] = repo_path
        deployment_context["filename"]     = repo_url.split("/")[-1]
        deployment_context["repo_url"]     = repo_url
        deployment_context["github_token"] = resolved_gh_token

        result = decide_and_execute(deployment_context)

        if user_id:
            dep_status = "success" if result.get("status") == "success" or result.get("endpoint") else "failed"
            await record_deployment(
                user_id=user_id,
                source_type="github",
                source_filename=repo_url.split("/")[-1],
                repo_url=repo_url,
                project_type=result.get("project_type") or review_output.get("type"),
                deployment_type=result.get("deployment"),
                status=dep_status,
                endpoint=result.get("endpoint") or result.get("url") or (result.get("details", {}) or {}).get("url"),
                app_id=result.get("app_id"),
                aws_service=result.get("deployment", "amplify").split("_")[0] if result.get("deployment") else "amplify",
                error_message=result.get("error")
            )
        return result

    except Exception as e:
        print("---------------- ERROR TRACEBACK ----------------")
        traceback.print_exc()
        print("------------------------------------------------")
        if user_id:
            try:
                await record_deployment(
                    user_id=user_id,
                    source_type="github",
                    repo_url=repo_url,
                    status="failed",
                    error_message=str(e)
                )
            except Exception:
                pass
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)