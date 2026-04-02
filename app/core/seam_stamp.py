import os
import random
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
    for i in range(num_pages):
        page = doc[i]
        strip_img = Image.open(strips[i])
        s_width, s_height = strip_img.size
        scale = 120.0 / Image.open(stamp_path).height
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
    output_path = pdf_path.replace(".pdf", "_seam.pdf")
    doc.save(output_path)
    doc.close()
    return output_path
