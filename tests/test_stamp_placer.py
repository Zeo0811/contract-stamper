import os
import fitz
from app.core.stamp_placer import place_stamp


def test_place_stamp(sample_pdf, sample_stamp):
    output = place_stamp(sample_pdf, sample_stamp, page_num=2, x=400, y=700)
    assert os.path.exists(output)
    doc = fitz.open(output)
    page = doc[2]
    images = page.get_images()
    assert len(images) >= 1
    doc.close()


def test_place_stamp_custom_size(sample_pdf, sample_stamp):
    output = place_stamp(sample_pdf, sample_stamp, page_num=0, x=300, y=400, size_mm=30.0)
    assert os.path.exists(output)
    doc = fitz.open(output)
    page = doc[0]
    images = page.get_images()
    assert len(images) >= 1
    doc.close()
