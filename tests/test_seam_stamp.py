import os
import fitz
from PIL import Image
from app.core.seam_stamp import slice_stamp, place_seam_stamps


def test_slice_stamp(sample_stamp):
    strips = slice_stamp(sample_stamp, num_pages=3)
    assert len(strips) == 3
    for strip_path in strips:
        assert os.path.exists(strip_path)
        img = Image.open(strip_path)
        assert img.mode == "RGBA"


def test_slice_stamp_widths(sample_stamp):
    strips = slice_stamp(sample_stamp, num_pages=5)
    assert len(strips) == 5
    original = Image.open(sample_stamp)
    total_width = sum(Image.open(s).width for s in strips)
    assert abs(total_width - original.width) < 20


def test_place_seam_stamps(sample_pdf, sample_stamp):
    output = place_seam_stamps(sample_pdf, sample_stamp)
    assert os.path.exists(output)
    doc = fitz.open(output)
    for i in range(len(doc)):
        page = doc[i]
        images = page.get_images()
        assert len(images) >= 1, f"Page {i} has no seam stamp"
    doc.close()
