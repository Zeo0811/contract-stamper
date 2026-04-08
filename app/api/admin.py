import json
import os
import shutil
import uuid
from datetime import date
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from app.auth import require_admin, list_users, create_user, delete_user
from app.config import DATA_DIR

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

STAMPS_DIR = os.path.join(DATA_DIR, "stamps")
STAMPS_META_FILE = os.path.join(DATA_DIR, "stamps_meta.json")


def _load_stamps_meta() -> list[dict]:
    if not os.path.exists(STAMPS_META_FILE):
        return []
    with open(STAMPS_META_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_stamps_meta(meta: list[dict]):
    os.makedirs(os.path.dirname(STAMPS_META_FILE), exist_ok=True)
    with open(STAMPS_META_FILE, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


# ── User management ──

@router.get("/users")
async def admin_list_users(user=Depends(require_admin)):
    return {"users": list_users()}


@router.post("/users")
async def admin_create_user(
    body: dict,
    user=Depends(require_admin),
):
    username = body.get("username", "").strip()
    password = body.get("password", "")
    role = body.get("role", "user")
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password required")
    result = create_user(username, password, role)
    return result


@router.delete("/users/{username}")
async def admin_delete_user(username: str, user=Depends(require_admin)):
    delete_user(username)
    return {"ok": True}


# ── Stamp management ──

@router.get("/stamps")
async def admin_list_stamps(user=Depends(require_admin)):
    meta = _load_stamps_meta()
    # Also scan directory for stamps not in meta
    os.makedirs(STAMPS_DIR, exist_ok=True)
    existing_files = {m["filename"] for m in meta}
    for f in sorted(os.listdir(STAMPS_DIR)):
        if f.lower().endswith(('.png', '.jpg', '.jpeg')) and f not in existing_files:
            meta.append({
                "filename": f,
                "company": os.path.splitext(f)[0],
                "created_at": str(date.today()),
            })
    # Filter out entries whose files no longer exist
    meta = [m for m in meta if os.path.exists(os.path.join(STAMPS_DIR, m["filename"]))]
    _save_stamps_meta(meta)
    stamps = []
    for m in meta:
        stamps.append({
            "filename": m["filename"],
            "company": m.get("company", ""),
            "created_at": m.get("created_at", ""),
            "url": f"/stamps/files/{m['filename']}",
        })
    return {"stamps": stamps}


@router.post("/stamps")
async def admin_upload_stamp(
    file: UploadFile = File(...),
    company: str = Form(...),
    user=Depends(require_admin),
):
    if not file.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
        raise HTTPException(status_code=400, detail="Only PNG/JPG files allowed")

    os.makedirs(STAMPS_DIR, exist_ok=True)
    ext = os.path.splitext(file.filename or ".png")[1].lower()
    filename = f"{uuid.uuid4().hex[:12]}{ext}"
    dest = os.path.join(STAMPS_DIR, filename)

    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    meta = _load_stamps_meta()
    meta.append({
        "filename": filename,
        "company": company,
        "created_at": str(date.today()),
    })
    _save_stamps_meta(meta)
    return {"filename": filename, "company": company, "url": f"/stamps/files/{filename}"}


@router.delete("/stamps/{filename}")
async def admin_delete_stamp(filename: str, user=Depends(require_admin)):
    filepath = os.path.join(STAMPS_DIR, filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    meta = _load_stamps_meta()
    meta = [m for m in meta if m["filename"] != filename]
    _save_stamps_meta(meta)
    return {"ok": True}
