import os
import time
import fitz
from PIL import Image, ImageDraw
from fastapi.testclient import TestClient


def _create_test_pdf(tmp_path) -> str:
    doc = fitz.open()
    for i in range(3):
        page = doc.new_page(width=595, height=842)
        tw = fitz.TextWriter(page.rect)
        tw.append((72, 72), f"Page {i + 1}", fontsize=14)
        if i == 2:
            tw.append((350, 700), "乙方（盖章）：", fontsize=12)
        tw.write_text(page)
    path = str(tmp_path / "test.pdf")
    doc.save(path)
    doc.close()
    return path


def _create_test_stamp(tmp_path) -> str:
    img = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([10, 10, 190, 190], outline=(200, 0, 0, 230), width=6)
    path = str(tmp_path / "stamp.png")
    img.save(path)
    return path


def test_full_workflow(tmp_path, monkeypatch):
    monkeypatch.setenv("API_KEY", "test-key")
    monkeypatch.setenv("WEB_PASSWORD", "test-pass")

    # Patch UPLOAD_DIR in all modules that import it
    monkeypatch.setattr("app.config.UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr("app.main.UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr("app.api.upload.UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr("app.api.detect.UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr("app.api.stamp.UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr("app.core.pdf_processor.UPLOAD_DIR", str(tmp_path))

    # Patch API_KEY in auth module (imported at module level)
    monkeypatch.setattr("app.config.API_KEY", "test-key")
    monkeypatch.setattr("app.auth.API_KEY", "test-key")

    from app.main import app
    client = TestClient(app)
    headers = {"Authorization": "Bearer test-key"}

    # Upload PDF
    pdf_path = _create_test_pdf(tmp_path)
    with open(pdf_path, "rb") as f:
        resp = client.post("/api/v1/upload", files={"file": ("test.pdf", f)}, headers=headers)
    assert resp.status_code == 200
    file_id = resp.json()["file_id"]
    assert resp.json()["page_count"] == 3

    # Upload stamp
    stamp_path = _create_test_stamp(tmp_path)
    with open(stamp_path, "rb") as f:
        resp = client.post("/api/v1/upload/stamp", files={"file": ("stamp.png", f)}, headers=headers)
    assert resp.status_code == 200
    stamp_id = resp.json()["stamp_id"]

    # Detect keywords
    resp = client.post("/api/v1/detect", json={"file_id": file_id}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["found"] is True

    # Stamp
    pos = resp.json()["positions"][0]
    resp = client.post("/api/v1/stamp", json={
        "file_id": file_id,
        "stamp_id": stamp_id,
        "party_b_position": {"page": pos["page"], "x": pos["x"], "y": pos["y"]},
        "riding_seam": True,
        "scan_effect": 50,
    }, headers=headers)
    assert resp.status_code == 200
    task_id = resp.json()["task_id"]

    # Poll until done
    for _ in range(30):
        resp = client.get(f"/api/v1/result/{task_id}", headers=headers)
        if resp.json()["status"] == "completed":
            break
        time.sleep(0.5)

    assert resp.json()["status"] == "completed"

    # Download
    resp = client.get(f"/api/v1/download/{task_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
