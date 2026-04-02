import os
from app.core.pdf_processor import get_page_count, render_page_preview


def test_get_page_count(sample_pdf):
    assert get_page_count(sample_pdf) == 3


def test_render_page_preview(sample_pdf, tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.pdf_processor.UPLOAD_DIR", str(tmp_path))
    path = render_page_preview(sample_pdf, 0)
    assert os.path.exists(path)
    assert path.endswith(".png")
