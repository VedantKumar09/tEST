"""
Auth Routes — Login with JWT, demo users
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from jose import jwt
from datetime import datetime, timedelta
from ..config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Demo users (replace with real DB in production)
DEMO_USERS = {
    "student@mindmesh.ai": {
        "password": "student123",
        "role": "student",
        "name": "Demo Student",
        "id": "student_001",
    },
    "admin@mindmesh.ai": {
        "password": "admin123",
        "role": "admin",
        "name": "Admin User",
        "id": "admin_001",
    },
}


class LoginRequest(BaseModel):
    email: str
    password: str
    role: str


def create_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


@router.post("/login")
async def login(body: LoginRequest):
    user = DEMO_USERS.get(body.email)
    if not user or user["password"] != body.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if user["role"] != body.role:
        raise HTTPException(status_code=403, detail=f"Account is not a {body.role}")

    token = create_token({"sub": body.email, "role": user["role"], "name": user["name"]})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"email": body.email, "name": user["name"], "role": user["role"]},
    }


@router.get("/me")
async def me():
    return {"message": "Token valid"}
