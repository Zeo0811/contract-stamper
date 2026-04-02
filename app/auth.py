from fastapi import Depends, HTTPException, Request, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import API_KEY, WEB_PASSWORD

bearer_scheme = HTTPBearer(auto_error=False)


async def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    if credentials is None or credentials.credentials != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return credentials.credentials


def verify_web_password(request: Request) -> bool:
    session_token = request.cookies.get("session_token")
    if session_token == WEB_PASSWORD:
        return True
    return False


def set_web_session(response: Response):
    response.set_cookie(
        key="session_token",
        value=WEB_PASSWORD,
        max_age=86400,
        httponly=True,
        samesite="lax",
    )
