import os
import fitz
from app.config import UPLOAD_DIR


def get_page_count(pdf_path: str) -> int:
    doc = fitz.open(pdf_path)
    count = len(doc)
    doc.close()
    return count


def render_page_preview(pdf_path: str, page_num: int, dpi: int = 150) -> str:
    doc = fitz.open(pdf_path)
    page = doc[page_num]
    pix = page.get_pixmap(dpi=dpi)
    preview_dir = os.path.join(UPLOAD_DIR, "previews")
    os.makedirs(preview_dir, exist_ok=True)
    filename = f"{os.path.basename(pdf_path)}_{page_num}.png"
    out_path = os.path.join(preview_dir, filename)
    pix.save(out_path)
    doc.close()
    return out_path


def render_all_previews(pdf_path: str, dpi: int = 150) -> list[str]:
    count = get_page_count(pdf_path)
    return [render_page_preview(pdf_path, i, dpi) for i in range(count)]
