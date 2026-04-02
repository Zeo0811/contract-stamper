import os
import tempfile
import fitz

KEYWORDS_BY_PARTY = {
    "乙方": [
        "乙方（盖章）", "乙方签章", "乙方（签字/盖章）",
        "乙方（签字盖章）", "乙方(盖章)", "乙方(签字/盖章)",
    ],
    "甲方": [
        "甲方（盖章）", "甲方签章", "甲方（签字/盖章）",
        "甲方（签字盖章）", "甲方(盖章)", "甲方(签字/盖章)",
    ],
}


def detect_keywords(pdf_path: str, party: str = "乙方") -> list[dict]:
    keywords = KEYWORDS_BY_PARTY.get(party, KEYWORDS_BY_PARTY["乙方"])
    doc = fitz.open(pdf_path)
    results = []
    for page_num in range(len(doc)):
        page = doc[page_num]
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
    doc.close()
    return results


def place_stamp(pdf_path: str, stamp_path: str, page_num: int, x: float, y: float, size_mm: float = 42.0) -> str:
    doc = fitz.open(pdf_path)
    page = doc[page_num]
    size_pt = size_mm * 2.835
    half = size_pt / 2
    stamp_rect = fitz.Rect(x - half, y - half, x + half, y + half)
    page.insert_image(stamp_rect, filename=stamp_path, overlay=True)
    fd, output_path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    doc.save(output_path)
    doc.close()
    return output_path
