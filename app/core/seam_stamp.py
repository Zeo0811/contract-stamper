import os
import random
import shutil
import tempfile
import fitz
from PIL import Image


def slice_stamp(stamp_path: str, num_pages: int) -> list[str]:
    img = Image.open(stamp_path).convert("RGBA")
    width, height = img.size
    strip_width = width // num_pages
    strips = []
    tmp_dir = tempfile.mkdtemp()
    for i in range(num_pages):
        left = i * strip_width
        right = left + strip_width if i < num_pages - 1 else width
        strip = img.crop((left, 0, right, height))
        angle = random.uniform(-0.5, 0.5)
        strip = strip.rotate(angle, expand=True, fillcolor=(0, 0, 0, 0))
        strip_path_out = os.path.join(tmp_dir, f"strip_{i}.png")
        strip.save(strip_path_out)
        strips.append(strip_path_out)
    return strips


def place_seam_stamps(pdf_path: str, stamp_path: str) -> str:
    doc = fitz.open(pdf_path)
    num_pages = len(doc)
    strips = slice_stamp(stamp_path, num_pages)
    stamp_img_original = Image.open(stamp_path)
    stamp_height = stamp_img_original.height
    for i in range(num_pages):
        page = doc[i]
        strip_img = Image.open(strips[i])
        s_width, s_height = strip_img.size
        scale = 120.0 / stamp_height
        display_w = s_width * scale
        display_h = s_height * scale
        page_w = page.rect.width
        page_h = page.rect.height
        v_offset = random.uniform(-3, 3)
        h_offset = random.uniform(-2, 2)
        x0 = page_w - display_w + h_offset
        y0 = (page_h - display_h) / 2 + v_offset
        x1 = page_w + h_offset
        y1 = y0 + display_h
        stamp_rect = fitz.Rect(x0, y0, x1, y1)
        page.insert_image(stamp_rect, filename=strips[i], overlay=True)
    fd, output_path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    doc.save(output_path)
    doc.close()
    # Clean up strip temp files
    for strip_path in strips:
        if os.path.exists(strip_path):
            os.unlink(strip_path)
    strip_dir = os.path.dirname(strips[0]) if strips else None
    if strip_dir and os.path.exists(strip_dir):
        shutil.rmtree(strip_dir, ignore_errors=True)
    return output_path
