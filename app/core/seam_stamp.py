import io
import os
import random
import shutil
import tempfile
import fitz
from PIL import Image


MAX_STAMP_PX = 500  # Max stamp dimension before slicing


def slice_stamp(stamp_path: str, num_pages: int) -> list[str]:
    img = Image.open(stamp_path).convert("RGBA")
    w, h = img.size
    if max(w, h) > MAX_STAMP_PX:
        scale = MAX_STAMP_PX / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    width, height = img.size
    strip_width = width // num_pages
    strips = []
    tmp_dir = tempfile.mkdtemp()
    for i in range(num_pages):
        left = i * strip_width
        right = left + strip_width if i < num_pages - 1 else width
        strip = img.crop((left, 0, right, height))
        angle = random.uniform(-1.5, 1.5)
        strip = strip.rotate(angle, expand=True, fillcolor=(0, 0, 0, 0))
        strip_path_out = os.path.join(tmp_dir, f"strip_{i}.png")
        strip.save(strip_path_out)
        strips.append(strip_path_out)
    return strips


def place_seam_stamps(pdf_path: str, stamp_path: str) -> str:
    doc = fitz.open(pdf_path)
    num_pages = len(doc)
    strips = slice_stamp(stamp_path, num_pages)
    # Get the actual downscaled stamp height from the first strip (before rotation padding)
    # Target: stamp displays at 120pt (≈42mm) high in PDF
    target_h = 120.0
    for i in range(num_pages):
        page = doc[i]
        strip_img = Image.open(strips[i])
        s_width, s_height = strip_img.size
        scale = target_h / s_height
        display_w = s_width * scale
        display_h = target_h
        page_w = page.rect.width
        page_h = page.rect.height
        v_offset = random.uniform(-8, 8)
        h_offset = random.uniform(-4, 4)
        x0 = page_w - display_w + h_offset
        y0 = (page_h - display_h) / 2 + v_offset
        x1 = page_w + h_offset
        y1 = y0 + display_h
        stamp_rect = fitz.Rect(x0, y0, x1, y1)
        # Read strip bytes to insert as stream (avoids embedding full-size file)
        with open(strips[i], "rb") as sf:
            strip_bytes = sf.read()
        page.insert_image(stamp_rect, stream=strip_bytes, overlay=True)
    fd, output_path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    doc.save(output_path, deflate=True, garbage=4)
    doc.close()
    # Clean up strip temp files
    for strip_path in strips:
        if os.path.exists(strip_path):
            os.unlink(strip_path)
    strip_dir = os.path.dirname(strips[0]) if strips else None
    if strip_dir and os.path.exists(strip_dir):
        shutil.rmtree(strip_dir, ignore_errors=True)
    return output_path
