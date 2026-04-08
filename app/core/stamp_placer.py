import io
import os
import random
import tempfile
import fitz
import numpy as np
from PIL import Image, ImageFilter, ImageEnhance

try:
    import pytesseract
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False

def _generate_keywords(party: str) -> list[str]:
    """Generate keyword variations covering different bracket/punctuation styles."""
    # Common seal-related suffixes
    suffixes = [
        "（盖章）", "(盖章)", "（盖章)", "(盖章）",
        "签章", "盖章",
        "（签字/盖章）", "(签字/盖章)", "（签字/盖章)", "(签字/盖章）",
        "（签字盖章）", "(签字盖章)", "（签字盖章)", "(签字盖章）",
        "（签章）", "(签章)", "（签章)", "(签章）",
        "（签字或盖章）", "(签字或盖章)",
        "（公章）", "(公章)", "（公章)", "(公章）",
        " （盖章）", " (盖章)", "（ 盖章 ）", "( 盖章 )",
        "（签字 / 盖章）", "(签字 / 盖章)",
    ]
    keywords = []
    for s in suffixes:
        keywords.append(party + s)
    return keywords


KEYWORDS_BY_PARTY = {
    "乙方": _generate_keywords("乙方"),
    "甲方": _generate_keywords("甲方"),
}


def _normalize_text(text: str) -> str:
    """Normalize Unicode punctuation for comparison."""
    replacements = {
        "\uff08": "(", "\uff09": ")",  # fullwidth parens
        "\u3008": "(", "\u3009": ")",  # angle brackets
        "\uff0f": "/",                 # fullwidth slash
        "\u3000": " ",                 # ideographic space
        "\u00a0": " ",                 # non-breaking space
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def _ocr_page(page, dpi: int = 300) -> list[dict]:
    """Run Tesseract OCR on a PDF page, return list of {text, x0, y0, x1, y1} in PDF points."""
    if not HAS_TESSERACT:
        return []
    pix = page.get_pixmap(dpi=dpi)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    # Get word-level bounding boxes from Tesseract
    data = pytesseract.image_to_data(img, lang="chi_sim+eng", output_type=pytesseract.Output.DICT)
    # Scale factor from image pixels back to PDF points
    scale = 72.0 / dpi
    words = []
    for i in range(len(data["text"])):
        txt = data["text"][i].strip()
        if not txt:
            continue
        words.append({
            "text": txt,
            "x0": data["left"][i] * scale,
            "y0": data["top"][i] * scale,
            "x1": (data["left"][i] + data["width"][i]) * scale,
            "y1": (data["top"][i] + data["height"][i]) * scale,
        })
    return words


def _search_ocr_words(ocr_words: list[dict], keyword: str) -> list[dict]:
    """Search for keyword in OCR results, merging adjacent word boxes."""
    if not ocr_words:
        return []
    # Build full text with position mapping
    full_text = ""
    char_to_word = []  # maps each char index -> word index
    for wi, w in enumerate(ocr_words):
        for ch in w["text"]:
            char_to_word.append(wi)
            full_text += ch
    norm_full = _normalize_text(full_text)
    norm_kw = _normalize_text(keyword)
    results = []
    start = 0
    while True:
        idx = norm_full.find(norm_kw, start)
        if idx == -1:
            break
        end_idx = idx + len(norm_kw) - 1
        # Find bounding box spanning matched words
        first_word = char_to_word[idx]
        last_word = char_to_word[end_idx]
        x0 = min(ocr_words[i]["x0"] for i in range(first_word, last_word + 1))
        y0 = min(ocr_words[i]["y0"] for i in range(first_word, last_word + 1))
        x1 = max(ocr_words[i]["x1"] for i in range(first_word, last_word + 1))
        y1 = max(ocr_words[i]["y1"] for i in range(first_word, last_word + 1))
        results.append({"x0": x0, "y0": y0, "x1": x1, "y1": y1})
        start = idx + 1
    return results


STAMP_OFFSET_Y = 60  # points below keyword text bottom to stamp center (~21mm)


def _make_result(keyword, page_num, rect_x0, rect_y0, rect_w, rect_h,
                  page_w, page_h, ocr=False):
    """Build a detection result with both absolute and normalized coordinates."""
    # Stamp center in PDF points
    cx = rect_x0 + rect_w / 2
    cy = rect_y0 + rect_h + STAMP_OFFSET_Y
    return {
        "keyword": keyword,
        "page": page_num,
        "x": round(cx),            # PDF points (backward compat)
        "y": round(cy),            # PDF points (backward compat)
        "x_norm": cx / page_w,     # 0.0 – 1.0, fraction of page width
        "y_norm": cy / page_h,     # 0.0 – 1.0, fraction of page height
        "width": round(rect_w),
        "height": round(rect_h),
        **({"ocr": True} if ocr else {}),
    }


def detect_keywords(pdf_path: str, party: str = "乙方") -> list[dict]:
    """Detect seal-placement keywords in PDF.

    Scans from the LAST page backward because contracts typically
    have the signature/seal block at the end.  Returns normalized
    (0-1) stamp-center coordinates offset below the keyword text.
    """
    keywords = KEYWORDS_BY_PARTY.get(party, KEYWORDS_BY_PARTY["乙方"])
    doc = fitz.open(pdf_path)
    results = []

    for page_num in reversed(range(len(doc))):
        page = doc[page_num]
        page_w = page.rect.width
        page_h = page.rect.height
        page_results = []

        # ── Pass 1: direct PyMuPDF text search ──
        for keyword in keywords:
            rects = page.search_for(keyword)
            for rect in rects:
                page_results.append(_make_result(
                    keyword, page_num,
                    rect.x0, rect.y0, rect.width, rect.height,
                    page_w, page_h,
                ))

        # ── Pass 2: normalized text fallback ──
        if not page_results:
            page_text = page.get_text()
            normalized = _normalize_text(page_text)
            for keyword in keywords:
                norm_kw = _normalize_text(keyword)
                if norm_kw in normalized:
                    rects = page.search_for(norm_kw)
                    if not rects:
                        rects = page.search_for(keyword)
                    for rect in rects:
                        page_results.append(_make_result(
                            keyword, page_num,
                            rect.x0, rect.y0, rect.width, rect.height,
                            page_w, page_h,
                        ))

        # ── Pass 3: OCR fallback for scanned pages ──
        if not page_results:
            page_text = page.get_text().strip()
            if len(page_text) < 50 and HAS_TESSERACT:
                ocr_words = _ocr_page(page)
                for keyword in keywords:
                    boxes = _search_ocr_words(ocr_words, keyword)
                    for box in boxes:
                        page_results.append(_make_result(
                            keyword, page_num,
                            box["x0"], box["y0"],
                            box["x1"] - box["x0"], box["y1"] - box["y0"],
                            page_w, page_h, ocr=True,
                        ))
                    if page_results:
                        break

        if page_results:
            page_results.sort(key=lambda r: r["y_norm"], reverse=True)
            results = page_results
            break

    doc.close()
    return results


MAX_STAMP_PX = 500  # Max stamp dimension in pixels


def _age_stamp(img: Image.Image) -> Image.Image:
    """Make a stamp image look like a heavily used, scanned seal impression.

    Simulates: strong ink fade, uneven pressure, blur, noise, micro-rotation.
    Input must be RGBA.
    """
    w, h = img.size

    # ── 1. Heavy desaturation: washed-out ink look ──
    rgb = img.convert("RGB")
    enhancer = ImageEnhance.Color(rgb)
    rgb = enhancer.enhance(random.uniform(0.30, 0.50))  # 30-50% saturation

    # ── 2. Brightness boost to wash out the color (lighter = more faded) ──
    enhancer = ImageEnhance.Brightness(rgb)
    rgb = enhancer.enhance(random.uniform(1.10, 1.30))

    # ── 3. Lower contrast for that flat scanned look ──
    enhancer = ImageEnhance.Contrast(rgb)
    rgb = enhancer.enhance(random.uniform(0.60, 0.80))

    # Merge back with original alpha
    img = Image.merge("RGBA", (*rgb.split(), img.split()[3]))

    # ── 4. Aggressive uneven ink distribution (pressure map) ──
    arr = np.array(img, dtype=np.float32)
    alpha = arr[:, :, 3]
    small_h, small_w = max(4, h // 30), max(4, w // 30)
    pressure = np.random.uniform(0.35, 1.0, (small_h, small_w)).astype(np.float32)
    pressure_img = Image.fromarray((pressure * 255).astype(np.uint8), mode="L")
    pressure_map = np.array(
        pressure_img.resize((w, h), Image.BILINEAR), dtype=np.float32
    ) / 255.0
    alpha = alpha * pressure_map
    # Overall transparency reduction
    alpha = alpha * random.uniform(0.55, 0.75)
    arr[:, :, 3] = alpha
    img = Image.fromarray(arr.astype(np.uint8), "RGBA")

    # ── 5. Stronger Gaussian blur (ink bleed on paper) ──
    blur_r = random.uniform(0.7, 1.3)
    img = img.filter(ImageFilter.GaussianBlur(radius=blur_r))

    # ── 6. Heavier noise on stamp pixels ──
    arr = np.array(img, dtype=np.float32)
    mask = arr[:, :, 3] > 10
    noise = np.random.normal(0, 8, (h, w, 3))
    for c in range(3):
        channel = arr[:, :, c]
        channel[mask] = np.clip(channel[mask] + noise[:, :, c][mask], 0, 255)
        arr[:, :, c] = channel
    img = Image.fromarray(arr.astype(np.uint8), "RGBA")

    # ── 7. Micro-rotation (hand shake) ──
    angle = random.uniform(-2.5, 2.5)
    img = img.rotate(angle, expand=True, fillcolor=(0, 0, 0, 0))

    return img


def _prepare_stamp(stamp_path: str) -> bytes:
    """Load, downscale, age, and return stamp as PNG bytes."""
    img = Image.open(stamp_path).convert("RGBA")
    w, h = img.size
    if max(w, h) > MAX_STAMP_PX:
        scale = MAX_STAMP_PX / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    img = _age_stamp(img)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def place_stamp(pdf_path: str, stamp_path: str, page_num: int, x: float, y: float, size_mm: float = 42.0) -> str:
    doc = fitz.open(pdf_path)
    page = doc[page_num]
    size_pt = size_mm * 2.835
    half = size_pt / 2
    stamp_rect = fitz.Rect(x - half, y - half, x + half, y + half)
    stamp_bytes = _prepare_stamp(stamp_path)
    page.insert_image(stamp_rect, stream=stamp_bytes, overlay=True)
    fd, output_path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    doc.save(output_path, deflate=True, garbage=4)
    doc.close()
    return output_path
