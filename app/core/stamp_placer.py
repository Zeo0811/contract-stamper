import io
import os
import tempfile
import fitz
from PIL import Image

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


def detect_keywords(pdf_path: str, party: str = "乙方") -> list[dict]:
    keywords = KEYWORDS_BY_PARTY.get(party, KEYWORDS_BY_PARTY["乙方"])
    doc = fitz.open(pdf_path)
    results = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        # First try direct search for each keyword
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
        # If no results yet, try with normalized text matching
        if not results:
            page_text = page.get_text()
            normalized = _normalize_text(page_text)
            for keyword in keywords:
                norm_kw = _normalize_text(keyword)
                if norm_kw in normalized:
                    # Found in normalized text, search with normalized keyword
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
