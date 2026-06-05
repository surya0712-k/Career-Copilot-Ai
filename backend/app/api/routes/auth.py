import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import create_access_token, get_current_user
from app.config import get_settings
from app.db.session import get_db
from app.models import Profile, User
from app.schemas import GitHubAuthRequest, TokenResponse, UserResponse

router = APIRouter()
settings = get_settings()


@router.post("/github", response_model=TokenResponse)
async def github_auth(body: GitHubAuthRequest, db: AsyncSession = Depends(get_db)):
    if not settings.github_client_id or not settings.github_client_secret:
        raise HTTPException(status_code=500, detail="GitHub OAuth not configured")

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "code": body.code,
            },
        )
        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="Failed to get GitHub access token")

        user_resp = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        user_resp.raise_for_status()
        gh_user = user_resp.json()

    result = await db.execute(select(User).where(User.github_id == str(gh_user["id"])))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            github_id=str(gh_user["id"]),
            github_username=gh_user["login"],
            email=gh_user.get("email"),
            avatar_url=gh_user.get("avatar_url"),
            github_access_token=access_token,
        )
        db.add(user)
        await db.flush()
        profile = Profile(user_id=user.id)
        db.add(profile)
    else:
        user.github_access_token = access_token
        user.avatar_url = gh_user.get("avatar_url")
        user.email = gh_user.get("email") or user.email

    await db.flush()
    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    return UserResponse.model_validate(user)
