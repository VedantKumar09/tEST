"""
Auth Routes — Login with JWT, student & admin roles
"""
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from pydantic import BaseModel

from ..config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])
security = HTTPBearer()

# ── Demo users ────────────────────────────────────────────────────────────────
DEMO_USERS = {
    "student@mindmesh.ai": {
        "email": "student@mindmesh.ai",
        "password": "student123",
        "name": "Demo Student",
        "role": "student",
    },
    "admin@mindmesh.ai": {
        "email": "admin@mindmesh.ai",
        "password": "admin123",
        "name": "Admin User",
        "role": "admin",
    },
}


# ── Pydantic schemas ──────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    email: str
    password: str
    role: str  # "student" | "admin"


class UserOut(BaseModel):
    email: str
    name: str
    role: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ── Helpers ───────────────────────────────────────────────────────────────────
def create_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    try:
        return jwt.decode(
            credentials.credentials,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


# ── Endpoints ─────────────────────────────────────────────────────────────────
@router.post("/login", response_model=TokenOut)
async def login(body: LoginRequest):
    user = DEMO_USERS.get(body.email.lower())
    if not user or user["password"] != body.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if user["role"] != body.role:
        raise HTTPException(status_code=401, detail=f"Account is not a {body.role}")

    token = create_token({"sub": user["email"], "name": user["name"], "role": user["role"]})
    return TokenOut(
        access_token=token,
        user=UserOut(email=user["email"], name=user["name"], role=user["role"]),
    )


@router.get("/me", response_model=UserOut)
async def me(payload: dict = Depends(verify_token)):
    return UserOut(email=payload["sub"], name=payload["name"], role=payload["role"])
