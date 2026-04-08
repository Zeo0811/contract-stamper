import io
import os
import tempfile
import fitz
from PIL import Image

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
    # Also add standalone party name as lowest-priority fallback
    keywords.append(party)
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


def detect_keywords(pdf_path: str, party: str = "乙方") -> list[dict]:
    keywords = KEYWORDS_BY_PARTY.get(party, KEYWORDS_BY_PARTY["乙方"])
    doc = fitz.open(pdf_path)
    results = []

    for page_num in range(len(doc)):
        page = doc[page_num]

        # ── Pass 1: direct PyMuPDF text search ──
        for keyword in keywords:
            rects = page.search_for(keyword)
            for rect in rects:
                results.append({
                    "keyword": keyword,
                    "page": page_num,
                    "x": round(rect.x0),
                    "y": round(rect.y0),
                    "width": round(rect.width),
                    "height": round(rect.height),
                })

        # ── Pass 2: normalized text fallback ──
        if not results:
            page_text = page.get_text()
            normalized = _normalize_text(page_text)
            for keyword in keywords:
                norm_kw = _normalize_text(keyword)
                if norm_kw in normalized:
                    rects = page.search_for(norm_kw)
                    if not rects:
                        rects = page.search_for(keyword)
                    for rect in rects:
                        results.append({
                            "keyword": keyword,
                            "page": page_num,
                            "x": round(rect.x0),
                            "y": round(rect.y0),
                            "width": round(rect.width),
                            "height": round(rect.height),
                        })

        # ── Pass 3: OCR fallback for scanned pages ──
        if not results:
            page_text = page.get_text().strip()
            # If the page has very little text, it's likely a scanned image
            if len(page_text) < 50 and HAS_TESSERACT:
                ocr_words = _ocr_page(page)
                for keyword in keywords:
                    boxes = _search_ocr_words(ocr_words, keyword)
                    for box in boxes:
                        results.append({
                            "keyword": keyword,
                            "page": page_num,
                            "x": round(box["x0"]),
                            "y": round(box["y0"]),
                            "width": round(box["x1"] - box["x0"]),
                            "height": round(box["y1"] - box["y0"]),
                            "ocr": True,
                        })
                    if results:
                        break  # found match, stop searching more keywords

    doc.close()
    return results


MAX_STAMP_PX = 500  # Max stamp image dimension in pixels


def _downscale_stamp(stamp_path: str) -> bytes:
    """Downscale stamp image to reasonable size and return PNG bytes."""
    img = Image.open(stamp_path).convert("RGBA")
    w, h = img.size
    if max(w, h) > MAX_STAMP_PX:
        scale = MAX_STAMP_PX / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def place_stamp(pdf_path: str, stamp_path: str, page_num: int, x: float, y: float, size_mm: float = 42.0) -> str:
    doc = fitz.open(pdf_path)
    page = doc[page_num]
    size_pt = size_mm * 2.835
    half = size_pt / 2
    stamp_rect = fitz.Rect(x - half, y - half, x + half, y + half)
    stamp_bytes = _downscale_stamp(stamp_path)
    page.insert_image(stamp_rect, stream=stamp_bytes, overlay=True)
    fd, output_path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    doc.save(output_path, deflate=True, garbage=4)
    doc.close()
    return output_path
