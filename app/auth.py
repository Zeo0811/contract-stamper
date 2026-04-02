import re
import secrets
from fastapi import Depends, HTTPException, Request, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import API_KEY, WEB_PASSWORD

bearer_scheme = HTTPBearer(auto_error=False)

active_sessions: set[str] = set()


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
    """Accept either API key (Bearer token) or web session cookie."""
    if credentials and credentials.credentials == API_KEY:
        return True
    if verify_web_password(request):
        return True
    raise HTTPException(status_code=401, detail="Authentication required")


def verify_web_password(request: Request) -> bool:
    session_token = request.cookies.get("session_token")
    if session_token and session_token in active_sessions:
        return True
    return False


def set_web_session(response: Response):
    token = secrets.token_hex(32)
    active_sessions.add(token)
    response.set_cookie(
        key="session_token",
        value=token,
        max_age=86400,
        httponly=True,
        samesite="lax",
    )
