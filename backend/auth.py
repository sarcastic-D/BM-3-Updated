import os
import jwt
import bcrypt
from datetime import datetime, timezone, timedelta
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from database import db

JWT_SECRET = os.environ.get("JWT_SECRET", "brand-monitoring-dev-secret-change-me")
JWT_ALG = "HS256"
JWT_EXPIRE_HOURS = 24 * 7

security = HTTPBearer(auto_error=False)

# Role hierarchy / permissions
ROLES = ["super_admin", "tenant_admin", "analyst", "viewer"]

# Which roles may access admin-configuration surfaces
ADMIN_CONFIG_ROLES = {"super_admin"}
MANAGE_USERS_ROLES = {"super_admin", "tenant_admin"}
WRITE_INVESTIGATION_ROLES = {"super_admin", "tenant_admin", "analyst"}


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_token(user: dict) -> str:
    payload = {
        "sub": user["id"],
        "email": user["email"],
        "role": user["role"],
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


async def get_current_user(creds: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    if not creds:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(creds.credentials, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
    if not user or user.get("status") != "Active":
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


def require_roles(*roles):
    async def checker(user: dict = Depends(get_current_user)):
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return checker


def tenant_scope(user: dict):
    """Return None if user can see all tenants, else list of allowed tenant ids."""
    if user["role"] == "super_admin":
        return None
    return user.get("tenant_ids", [])
