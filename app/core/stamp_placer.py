import fitz

KEYWORDS = [
    "乙方（盖章）",
    "乙方签章",
    "乙方（签字/盖章）",
    "乙方（签字盖章）",
    "乙方(盖章)",
    "乙方(签字/盖章)",
]


def detect_keywords(pdf_path: str) -> list[dict]:
    doc = fitz.open(pdf_path)
    results = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        for keyword in KEYWORDS:
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
    output_path = pdf_path.replace(".pdf", "_stamped.pdf")
    doc.save(output_path)
    doc.close()
    return output_path
