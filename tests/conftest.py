import os
import fitz
from PIL import Image
import pytest

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture
def sample_pdf(tmp_path):
    """Create a 3-page PDF with '乙方（盖章）' on page 3."""
    doc = fitz.open()
    for i in range(3):
        page = doc.new_page(width=595, height=842)  # A4
        tw = fitz.TextWriter(page.rect)
        tw.append((72, 72), f"Contract Page {i + 1}", fontsize=14)
        if i == 2:
            tw.append((350, 700), "乙方（盖章）：", fontsize=12)
        tw.write_text(page)
    path = tmp_path / "contract.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


@pytest.fixture
def sample_stamp(tmp_path):
    """Create a red circle stamp PNG with transparency."""
    img = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    draw.ellipse([10, 10, 190, 190], outline=(200, 0, 0, 230), width=6)
    draw.text((60, 90), "TEST", fill=(200, 0, 0, 230))
    path = tmp_path / "stamp.png"
    img.save(str(path))
    return str(path)
