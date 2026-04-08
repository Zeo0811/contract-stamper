import json
import os
import re
import asyncio
import time
import glob
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
from app.config import UPLOAD_DIR, DATA_DIR, FILE_TTL_SECONDS
from app.auth import (
    get_current_user, authenticate, init_users, require_auth,
    verify_auth, active_sessions,
)

from app.api.upload import router as upload_router
from app.api.detect import router as detect_router
from app.api.stamp import router as stamp_router
from app.api.result import router as result_router
from app.api.admin import router as admin_router

async def cleanup_old_files():
    while True:
        await asyncio.sleep(300)
        now = time.time()
        for directory in ["uploads", "stamps", "results", "previews"]:
            dir_path = os.path.join(UPLOAD_DIR, directory)
            if not os.path.exists(dir_path):
                continue
            for filepath in glob.glob(os.path.join(dir_path, "*")):
                if now - os.path.getmtime(filepath) > FILE_TTL_SECONDS:
                    os.remove(filepath)


@asynccontextmanager
async def lifespan(app_instance):
    init_users()
    task = asyncio.create_task(cleanup_old_files())
    yield
    task.cancel()


app = FastAPI(title="Contract Stamper", version="1.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(upload_router)
app.include_router(detect_router)
app.include_router(stamp_router)
app.include_router(result_router)
app.include_router(admin_router)

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(os.path.join(UPLOAD_DIR, "uploads"), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_DIR, "stamps"), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_DIR, "results"), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_DIR, "previews"), exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(os.path.join(DATA_DIR, "stamps"), exist_ok=True)

static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

# Cache-busting: changes every deployment so browsers fetch fresh static files
DEPLOY_VERSION = str(int(time.time()))

STAMPS_META_FILE = os.path.join(DATA_DIR, "stamps_meta.json")
DATA_STAMPS_DIR = os.path.join(DATA_DIR, "stamps")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/stamps/files/{filename}")
async def serve_stamp_file(filename: str):
    """Serve stamp images from persistent DATA_DIR."""
    if not re.match(r'^[a-zA-Z0-9._-]+$', filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = os.path.join(DATA_STAMPS_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404)
    return FileResponse(path)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    user = get_current_user(request)
    return templates.TemplateResponse("index.html", {
        "request": request,
        "authenticated": user is not None,
        "user": user,
        "v": DEPLOY_VERSION,
    })


@app.post("/api/v1/login")
async def login_api(body: dict):
    username = body.get("username", "")
    password = body.get("password", "")
    token = authenticate(username, password)
    if not token:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    response = JSONResponse({"token": token, "username": username})
    response.set_cookie(
        key="session_token",
        value=token,
        max_age=86400,
        httponly=False,
        samesite="lax",
    )
    return response


@app.post("/login")
async def login_form(username: str = Form(""), password: str = Form("")):
    token = authenticate(username, password)
    if not token:
        return RedirectResponse(url="/?error=1", status_code=303)
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        key="session_token",
        value=token,
        max_age=86400,
        httponly=False,
        samesite="lax",
    )
    return response


@app.get("/api/v1/me")
async def get_me(user=Depends(require_auth)):
    return {"username": user["username"], "role": user["role"]}


@app.post("/api/v1/logout")
async def logout(request: Request):
    token = request.cookies.get("session_token")
    if token and token in active_sessions:
        del active_sessions[token]
    response = JSONResponse({"ok": True})
    response.delete_cookie("session_token")
    return response


@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "user": user,
        "v": DEPLOY_VERSION,
    })


@app.get("/api/v1/stamps/list")
async def list_preset_stamps():
    """List all preset stamp images from DATA_DIR/stamps, with company metadata."""
    os.makedirs(DATA_STAMPS_DIR, exist_ok=True)

    # Load metadata
    meta = []
    if os.path.exists(STAMPS_META_FILE):
        with open(STAMPS_META_FILE, "r", encoding="utf-8") as f:
            meta = json.load(f)
    meta_map = {m["filename"]: m for m in meta}

    stamps = []
    for f in sorted(os.listdir(DATA_STAMPS_DIR)):
        if f.lower().endswith(('.png', '.jpg', '.jpeg')):
            m = meta_map.get(f, {})
            name = m.get("company", os.path.splitext(f)[0])
            stamps.append({
                "name": name,
                "company": name,
                "filename": f,
                "url": f"/stamps/files/{f}",
            })
    return {"stamps": stamps}


@app.get("/api/v1/preview/{filename}")
async def serve_preview(filename: str):
    if not re.match(r'^[a-zA-Z0-9._-]+$', filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = os.path.join(UPLOAD_DIR, "previews", filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404)
    return FileResponse(path)


if __name__ == "__main__":
    import uvicorn
    from app.config import PORT
    uvicorn.run(app, host="0.0.0.0", port=PORT)
