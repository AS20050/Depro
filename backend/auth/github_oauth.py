import os
import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.models import User
from db.database import async_session
from auth.jwt_handler import create_access_token

router = APIRouter(prefix="/auth/github", tags=["GitHub OAuth"])

GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")
GITHUB_REDIRECT_URI = "http://localhost:8000/auth/github/callback"


@router.get("")
async def github_login():
    """Redirect user to GitHub OAuth authorization page."""
    if not GITHUB_CLIENT_ID:
        raise HTTPException(status_code=500, detail="GitHub OAuth not configured. Set GITHUB_CLIENT_ID in .env")

    github_auth_url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={GITHUB_CLIENT_ID}"
        f"&redirect_uri={GITHUB_REDIRECT_URI}"
        f"&scope=user:email,repo,admin:repo_hook"
    )
    return RedirectResponse(url=github_auth_url)


@router.get("/callback")
async def github_callback(code: str):
    """Handle GitHub OAuth callback: exchange code for token, upsert user, return JWT."""

    # 1. Exchange code for access token
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            "https://github.com/login/oauth/access_token",
            json={
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": GITHUB_REDIRECT_URI
            },
            headers={"Accept": "application/json"}
        )

    token_data = token_response.json()
    github_access_token = token_data.get("access_token")

    if not github_access_token:
        error = token_data.get("error_description", "Failed to get access token")
        raise HTTPException(status_code=400, detail=error)

    # 2. Fetch GitHub user profile
    async with httpx.AsyncClient() as client:
        user_response = await client.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {github_access_token}",
                "Accept": "application/vnd.github.v3+json"
            }
        )

    if user_response.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to fetch GitHub profile")

    github_user = user_response.json()
    github_id = str(github_user["id"])
    username = github_user.get("login", f"gh-{github_id}")
    display_name = github_user.get("name", username)
    avatar_url = github_user.get("avatar_url", "")
    email = github_user.get("email")

    # 3. Fetch email if not public
    if not email:
        async with httpx.AsyncClient() as client:
            emails_response = await client.get(
                "https://api.github.com/user/emails",
                headers={
                    "Authorization": f"Bearer {github_access_token}",
                    "Accept": "application/vnd.github.v3+json"
                }
            )
        if emails_response.status_code == 200:
            emails = emails_response.json()
            primary = next((e for e in emails if e.get("primary")), None)
            if primary:
                email = primary["email"]

    # 4. Upsert user in database
    async with async_session() as db:
        result = await db.execute(select(User).where(User.github_id == github_id))
        user = result.scalar_one_or_none()

        if user:
            # Update existing user
            user.github_token = github_access_token
            user.avatar_url = avatar_url
            user.display_name = display_name
            if email and not user.email:
                user.email = email
        else:
            # Check if username is taken
            existing = await db.execute(select(User).where(User.username == username))
            if existing.scalar_one_or_none():
                username = f"{username}-{github_id[:6]}"

            user = User(
                email=email,
                username=username,
                display_name=display_name,
                avatar_url=avatar_url,
                github_id=github_id,
                github_token=github_access_token
            )
            db.add(user)

        await db.commit()
        await db.refresh(user)

        # 5. Create JWT and redirect to frontend
        jwt_token = create_access_token(str(user.id), user.username)

    # Redirect to frontend with token
    frontend_url = f"http://localhost:5173/auth/callback?token={jwt_token}"
    return RedirectResponse(url=frontend_url)
