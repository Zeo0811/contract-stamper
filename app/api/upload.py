import os
import uuid
import shutil
import asyncio
import subprocess
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from app.auth import verify_auth
from app.config import UPLOAD_DIR
from app.core.pdf_processor import get_page_count, render_all_previews

router = APIRouter(prefix="/api/v1")

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc"}


def _find_libreoffice() -> str:
    """Find LibreOffice binary (libreoffice on Linux, soffice on macOS)."""
    for cmd in ["libreoffice", "soffice"]:
        if shutil.which(cmd):
            return cmd
    raise RuntimeError("LibreOffice not found. Install it to convert Word documents.")


def _accept_tracked_changes(word_path: str, output_path: str) -> bool:
    """Accept all tracked changes, save to output_path. Returns True on success."""
    try:
        from docx import Document
        ns = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
        doc = Document(word_path)

        # Walk entire document XML and handle revision elements
        for elem in list(doc.element.body.iter()):
            tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
            parent = elem.getparent()
            if parent is None:
                continue
            if tag == 'ins':
                # Accept insertion: move children up, remove wrapper
                idx = list(parent).index(elem)
                for child in list(elem):
                    parent.insert(idx, child)
                    idx += 1
                parent.remove(elem)
            elif tag == 'del':
                # Accept deletion: remove entirely
                parent.remove(elem)
            elif tag in ('rPrChange', 'pPrChange', 'sectPrChange', 'tblPrChange', 'tblGridChange'):
                parent.remove(elem)

        doc.save(output_path)
        return True
    except Exception:
        return False


def _convert_word_to_pdf(word_path: str, output_dir: str) -> str:
    """Convert Word document to PDF using LibreOffice headless."""
    # Try to accept tracked changes (overwrite in-place since it's our copy)
    _accept_tracked_changes(word_path, word_path)

    lo_bin = _find_libreoffice()
    result = subprocess.run(
        [lo_bin, "--headless", "--convert-to", "pdf", "--outdir", output_dir, word_path],
        capture_output=True, text=True, timeout=120,
    )

    if result.returncode != 0:
        raise RuntimeError(f"LibreOffice conversion failed: {result.stderr}")

    # LibreOffice outputs filename with .pdf extension
    base = os.path.splitext(os.path.basename(word_path))[0]
    pdf_path = os.path.join(output_dir, f"{base}.pdf")
    if not os.path.exists(pdf_path):
        raise RuntimeError("Converted PDF not found")
    return pdf_path


@router.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    _: str = Depends(verify_auth),
):
    # Validate file extension
    filename = file.filename or ""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的文件格式，请上传 PDF 或 Word 文档")

    file_id = uuid.uuid4().hex[:12]
    upload_dir = os.path.join(UPLOAD_DIR, "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    # Save uploaded file with original extension
    raw_path = os.path.join(upload_dir, f"{file_id}{ext}")
    with open(raw_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Convert Word to PDF if needed
    if ext in (".docx", ".doc"):
        pdf_path = await asyncio.to_thread(_convert_word_to_pdf, raw_path, upload_dir)
        # Rename to standard file_id.pdf
        final_path = os.path.join(upload_dir, f"{file_id}.pdf")
        os.rename(pdf_path, final_path)
        os.remove(raw_path)  # Clean up original Word file
    else:
        final_path = raw_path  # Already PDF, but ensure naming
        if not raw_path.endswith(f"{file_id}.pdf"):
            final_path = os.path.join(upload_dir, f"{file_id}.pdf")
            os.rename(raw_path, final_path)

    page_count = await asyncio.to_thread(get_page_count, final_path)
    previews = await asyncio.to_thread(render_all_previews, final_path)
    preview_urls = [f"/api/v1/preview/{os.path.basename(p)}" for p in previews]
    return {
        "file_id": file_id,
        "page_count": page_count,
        "previews": preview_urls,
        "converted_from": ext if ext != ".pdf" else None,
    }


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
