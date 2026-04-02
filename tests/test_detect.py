import os
from app.core.pdf_processor import get_page_count, render_page_preview
from app.core.stamp_placer import detect_keywords


def test_get_page_count(sample_pdf):
    assert get_page_count(sample_pdf) == 3


def test_render_page_preview(sample_pdf, tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.pdf_processor.UPLOAD_DIR", str(tmp_path))
    path = render_page_preview(sample_pdf, 0)
    assert os.path.exists(path)
    assert path.endswith(".png")


def test_detect_keywords_found(sample_pdf):
    results = detect_keywords(sample_pdf)
    assert len(results) == 1
    assert results[0]["keyword"] == "乙方（盖章）"
    assert results[0]["page"] == 2
    assert results[0]["x"] > 0
    assert results[0]["y"] > 0


def test_detect_keywords_not_found(tmp_path):
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    tw = fitz.TextWriter(page.rect)
    tw.append((72, 72), "No keywords here", fontsize=12)
    tw.write_text(page)
    path = str(tmp_path / "empty.pdf")
    doc.save(path)
    doc.close()
    results = detect_keywords(path)
    assert len(results) == 0
