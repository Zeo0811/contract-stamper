import os
import uuid
import shutil
import asyncio
from fastapi import APIRouter, UploadFile, File, Depends
from app.auth import verify_auth
from app.config import UPLOAD_DIR
from app.core.pdf_processor import get_page_count, render_all_previews

router = APIRouter(prefix="/api/v1")


@router.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    _: str = Depends(verify_auth),
):
    file_id = uuid.uuid4().hex[:12]
    upload_dir = os.path.join(UPLOAD_DIR, "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{file_id}.pdf")
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    page_count = await asyncio.to_thread(get_page_count, file_path)
    previews = await asyncio.to_thread(render_all_previews, file_path)
    preview_urls = [f"/api/v1/preview/{os.path.basename(p)}" for p in previews]
    return {"file_id": file_id, "page_count": page_count, "previews": preview_urls}


@router.post("/upload/stamp")
async def upload_stamp(
    file: UploadFile = File(...),
    _: str = Depends(verify_auth),
):
    stamp_id = uuid.uuid4().hex[:12]
    stamp_dir = os.path.join(UPLOAD_DIR, "stamps")
    os.makedirs(stamp_dir, exist_ok=True)
    stamp_path = os.path.join(stamp_dir, f"{stamp_id}.png")
    with open(stamp_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"stamp_id": stamp_id}
