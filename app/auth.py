import hashlib
import json
import os
import re
import secrets
import time
from fastapi import Depends, HTTPException, Request, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import API_KEY, DATA_DIR

bearer_scheme = HTTPBearer(auto_error=False)

# In-memory session store: token -> {username, role, created_at}
active_sessions: dict[str, dict] = {}

USERS_FILE = os.path.join(DATA_DIR, "users.json")
TOKEN_TTL = 86400  # 24 hours


def _hash_password(password: str, salt: str = None) -> tuple[str, str]:
    if salt is None:
        salt = secrets.token_hex(16)
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return h, salt


def _load_users() -> list[dict]:
    if not os.path.exists(USERS_FILE):
        return []
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_users(users: list[dict]):
    os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


def init_users():
    """Ensure default admin user exists."""
    os.makedirs(DATA_DIR, exist_ok=True)
    users = _load_users()
    admin_exists = any(u["username"] == "admin" for u in users)
    if not admin_exists:
        admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
        h, salt = _hash_password(admin_password)
        users.append({
            "username": "admin",
            "password_hash": f"{salt}:{h}",
            "role": "admin",
        })
        _save_users(users)


def authenticate(username: str, password: str) -> str | None:
    """Verify credentials and return a session token, or None."""
    users = _load_users()
    for u in users:
        if u["username"] == username:
            salt, stored_hash = u["password_hash"].split(":", 1)
            h, _ = _hash_password(password, salt)
            if h == stored_hash:
                token = secrets.token_hex(32)
                active_sessions[token] = {
                    "username": u["username"],
                    "role": u["role"],
                    "created_at": time.time(),
                }
                return token
            return None
    return None


def get_current_user(request: Request) -> dict | None:
    """Extract user from Bearer token or session cookie."""
    token = None

    # Check Authorization header
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        token = auth[7:]

    # Check cookie
    if not token:
        token = request.cookies.get("session_token")

    if not token or token not in active_sessions:
        return None

    session = active_sessions[token]
    # Check expiry
    if time.time() - session["created_at"] > TOKEN_TTL:
        del active_sessions[token]
        return None

    return {"username": session["username"], "role": session["role"]}


async def require_auth(request: Request):
    """FastAPI dependency: returns user dict or raises 401."""
    user = get_current_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


async def require_admin(request: Request):
    """FastAPI dependency: returns user dict or raises 403."""
    user = get_current_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def validate_id(id_str: str) -> str:
    if not re.match(r'^[a-f0-9]+$', id_str):
        raise HTTPException(status_code=400, detail="Invalid ID format")
    return id_str


async def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    if credentials is None or credentials.credentials != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return credentials.credentials


async def verify_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    """Accept API key, user token, or web session cookie."""
    if credentials and credentials.credentials == API_KEY:
        return True
    if get_current_user(request):
        return True
    raise HTTPException(status_code=401, detail="Authentication required")


# User management helpers (used by admin API)
def list_users() -> list[dict]:
    users = _load_users()
    return [{"username": u["username"], "role": u["role"]} for u in users]


def create_user(username: str, password: str, role: str) -> dict:
    users = _load_users()
    if any(u["username"] == username for u in users):
        raise HTTPException(status_code=400, detail="User already exists")
    if role not in ("admin", "user"):
        raise HTTPException(status_code=400, detail="Role must be admin or user")
    h, salt = _hash_password(password)
    users.append({
        "username": username,
        "password_hash": f"{salt}:{h}",
        "role": role,
    })
    _save_users(users)
    return {"username": username, "role": role}


def delete_user(username: str):
    if username == "admin":
        raise HTTPException(status_code=400, detail="Cannot delete admin user")
    users = _load_users()
    new_users = [u for u in users if u["username"] != username]
    if len(new_users) == len(users):
        raise HTTPException(status_code=404, detail="User not found")
    _save_users(new_users)
