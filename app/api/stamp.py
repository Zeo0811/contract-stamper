import io
import os
import uuid
import shutil
import threading
import tempfile
import time
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.auth import verify_auth, validate_id
from app.config import UPLOAD_DIR
from app.core.stamp_placer import place_stamp, extract_party_names
from app.core.seam_stamp import place_seam_stamps
from app.core.scan_effect import scan_params_from_slider, apply_scan_to_image
import fitz
from PIL import Image

router = APIRouter(prefix="/api/v1")

# In-memory task store
tasks: dict[str, dict] = {}


class Position(BaseModel):
    page: int
    x: float
    y: float


class StampRequest(BaseModel):
    file_id: str
    stamp_id: str
    party_b_position: Position | None = None
    riding_seam: bool = True
    seam_position: str = "top"  # random, top, center, bottom
    scan_effect: int = 50  # 0=off, 1-39=heavy, 40-79=medium, 80-100=light
    stamp_aging: int = 70  # 0=off, 1-100=intensity of stamp aging effect
    original_filename: str = ""


def _process_stamp(task_id: str, req: StampRequest):
    try:
        tasks[task_id]["created_at"] = time.time()
        tasks[task_id]["status"] = "processing"
        pdf_path = os.path.join(UPLOAD_DIR, "uploads", f"{req.file_id}.pdf")

        # Extract party names for email subject
        try:
            parties = extract_party_names(pdf_path)
            tasks[task_id]["party_a"] = parties.get("party_a", "")
            tasks[task_id]["party_b"] = parties.get("party_b", "")
        except Exception:
            tasks[task_id]["party_a"] = ""
            tasks[task_id]["party_b"] = ""
        stamp_path = os.path.join(UPLOAD_DIR, "stamps", f"{req.stamp_id}.png")
        current_pdf = pdf_path

        # Step 1: Place party B stamp
        if req.party_b_position:
            current_pdf = place_stamp(
                current_pdf, stamp_path,
                page_num=req.party_b_position.page,
                x=req.party_b_position.x,
                y=req.party_b_position.y,
                stamp_aging=req.stamp_aging,
            )
            tasks[task_id]["progress"] = 30

        # Step 2: Place riding seam stamps
        if req.riding_seam:
            current_pdf = place_seam_stamps(
                current_pdf, stamp_path,
                stamp_aging=req.stamp_aging,
                position=req.seam_position,
            )
            tasks[task_id]["progress"] = 60

        # Step 3: Apply scan effect
        if req.scan_effect > 0:
            params = scan_params_from_slider(req.scan_effect)
            doc = fitz.open(current_pdf)
            processed_images = []
            for page_num in range(len(doc)):
                page = doc[page_num]
                pix = page.get_pixmap(dpi=params["dpi"])
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                processed = apply_scan_to_image(img, params)
                processed_images.append(processed)
            doc.close()

            result_doc = fitz.open()
            jpeg_quality = params.get("jpeg_quality", 80)
            for img in processed_images:
                w, h = img.size
                # A4 width in points, scale height proportionally
                page_w = 595.276
                page_h = page_w * h / w
                page = result_doc.new_page(width=page_w, height=page_h)
                # Encode as JPEG bytes and insert directly (keeps compression)
                buf = io.BytesIO()
                img.save(buf, "JPEG", quality=jpeg_quality)
                jpeg_bytes = buf.getvalue()
                page.insert_image(
                    fitz.Rect(0, 0, page_w, page_h),
                    stream=jpeg_bytes,
                )

            result_path = os.path.join(UPLOAD_DIR, "results", f"{task_id}.pdf")
            os.makedirs(os.path.dirname(result_path), exist_ok=True)
            result_doc.save(result_path, deflate=True, garbage=4)
            result_doc.close()
            current_pdf = result_path
        else:
            result_path = os.path.join(UPLOAD_DIR, "results", f"{task_id}.pdf")
            os.makedirs(os.path.dirname(result_path), exist_ok=True)
            shutil.copy2(current_pdf, result_path)
            current_pdf = result_path

        tasks[task_id]["status"] = "completed"
        tasks[task_id]["progress"] = 100
        tasks[task_id]["result_path"] = current_pdf

    except Exception as e:
        tasks[task_id]["status"] = "error"
        tasks[task_id]["error"] = str(e)


@router.post("/stamp")
async def stamp(
    req: StampRequest,
    _: str = Depends(verify_auth),
):
    validate_id(req.file_id)
    validate_id(req.stamp_id)
    # Clean up old completed/errored tasks older than 1 hour
    now = time.time()
    old_tasks = [tid for tid, t in tasks.items()
                 if t.get("created_at", 0) < now - 3600 and t.get("status") in ("completed", "error")]
    for tid in old_tasks:
        del tasks[tid]
    task_id = uuid.uuid4().hex[:12]
    tasks[task_id] = {"status": "pending", "progress": 0, "original_filename": req.original_filename}
    thread = threading.Thread(target=_process_stamp, args=(task_id, req))
    thread.start()
    return {"task_id": task_id}
