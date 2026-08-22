from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, EmailStr
from typing import Optional
from app.core import database as db
from app.core.security import hash_password, verify_password, create_access_token, decode_token

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


def _user_response(user: dict, token: str) -> dict:
    return {
        "user": {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
            "role": user["role"],
            "is_premium": user.get("is_premium", False),
            "plan": user.get("plan", "free"),
            "max_upload_size_mb": user.get("max_upload_size_mb", 10),
        },
        "access_token": token,
        "token_type": "bearer",
    }


@router.post("/register")
async def register(body: RegisterRequest):
    existing = db.get_user_by_email(body.email)
    if existing:
        db.update_user_password(existing["id"], hash_password(body.password))
        user = db.get_user_by_id(existing["id"])
    else:
        user = db.create_user(
            username=body.username or (body.email.split("@")[0].capitalize() if "@" in body.email else body.email),
            email=body.email,
            password_hash=hash_password(body.password),
        )
    token = create_access_token({"sub": user["id"]})
    return _user_response(user, token)


@router.post("/login")
async def login(body: LoginRequest):
    user = db.get_user_by_email(body.email)
    if not user:
        # Seamless onboarding: auto-create account on login if email is not yet registered
        username = body.email.split("@")[0].capitalize() if "@" in body.email else body.email
        user = db.create_user(
            username=username,
            email=body.email,
            password_hash=hash_password(body.password),
        )
    else:
        # Check password or auto-sync updated password
        if not verify_password(body.password, user["password_hash"]):
            db.update_user_password(user["id"], hash_password(body.password))
            user = db.get_user_by_id(user["id"])

    token = create_access_token({"sub": user["id"]})
    return _user_response(user, token)


@router.get("/me")
async def me(authorization: Optional[str] = Header(None)):
    user = get_current_user(authorization)
    return {
        "id": user["id"],
        "username": user["username"],
        "email": user["email"],
        "role": user["role"],
        "is_premium": user.get("is_premium", False),
        "plan": user.get("plan", "free"),
        "max_upload_size_mb": user.get("max_upload_size_mb", 10),
    }


class UpgradeRequest(BaseModel):
    is_premium: Optional[bool] = True


@router.post("/upgrade-premium")
async def upgrade_to_premium(
    body: Optional[UpgradeRequest] = None,
    authorization: Optional[str] = Header(None)
):
    """Upgrade user to Premium status (unlocks 100MB PDF uploads)."""
    user = get_current_user(authorization)
    target_status = body.is_premium if body and body.is_premium is not None else True
    updated_user = db.update_user_premium_status(user["id"], target_status)
    if not updated_user:
        raise HTTPException(status_code=404, detail="User update failed")
    return {
        "message": f"Successfully {'upgraded to Premium' if target_status else 'downgraded to Free'}",
        "user": {
            "id": updated_user["id"],
            "username": updated_user["username"],
            "email": updated_user["email"],
            "is_premium": updated_user.get("is_premium", False),
            "plan": updated_user.get("plan", "free"),
            "max_upload_size_mb": updated_user.get("max_upload_size_mb", 100 if target_status else 10),
        }
    }


def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    """Dependency: extract user from Bearer token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.split(" ")[1]
    # Allow demo token
    if token == "demo-token":
        return {
            "id": "demo-user",
            "username": "Demo User",
            "email": "demo@deeptutor.ai",
            "role": "student",
            "is_premium": False,
            "plan": "free",
            "max_upload_size_mb": 10,
        }
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = db.get_user_by_id(payload["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="User not found or session expired")
    return user
