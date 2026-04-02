# Contract Stamper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a web-based contract auto-stamping tool with keyword-based seal positioning, riding seam stamps, simulated scan effects, and RESTful API for skill/MCP integration.

**Architecture:** FastAPI backend handles PDF processing (PyMuPDF + Pillow) with async task execution. Vanilla HTML/CSS/JS frontend with PDF.js for preview and interaction. Docker-based deployment on Railway.

**Tech Stack:** Python 3.11, FastAPI, PyMuPDF (fitz), Pillow, PDF.js, Docker

---

## File Structure

```
contract-stamper/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app, mount routers + static files + templates
│   ├── config.py             # Settings from env vars (API_KEY, WEB_PASSWORD, PORT)
│   ├── auth.py               # API Key dependency + web password session middleware
│   ├── api/
│   │   ├── __init__.py
│   │   ├── upload.py         # POST /upload, POST /upload/stamp
│   │   ├── detect.py         # POST /detect
│   │   ├── stamp.py          # POST /stamp
│   │   └── result.py         # GET /result/{task_id}, GET /download/{task_id}
│   ├── core/
│   │   ├── __init__.py
│   │   ├── pdf_processor.py  # render_page_to_image(), images_to_pdf()
│   │   ├── stamp_placer.py   # detect_keywords(), place_stamp()
│   │   ├── seam_stamp.py     # slice_stamp(), place_seam_stamps()
│   │   └── scan_effect.py    # apply_scan_effect() with all sub-effects
│   ├── static/
│   │   ├── css/style.css
│   │   └── js/app.js
│   └── templates/
│       └── index.html
├── tests/
│   ├── __init__.py
│   ├── conftest.py           # shared fixtures (sample PDF, sample stamp PNG)
│   ├── test_detect.py
│   ├── test_stamp_placer.py
│   ├── test_seam_stamp.py
│   └── test_scan_effect.py
├── Dockerfile
├── requirements.txt
├── railway.toml
└── .env.example
```

---

### Task 1: Project Scaffolding + Config

**Files:**
- Create: `app/__init__.py`, `app/config.py`, `app/main.py`, `requirements.txt`, `.env.example`, `app/api/__init__.py`, `app/core/__init__.py`, `tests/__init__.py`

- [ ] **Step 1: Create requirements.txt**

```
fastapi==0.115.0
uvicorn==0.30.0
PyMuPDF==1.24.0
Pillow==10.4.0
python-multipart==0.0.9
```

- [ ] **Step 2: Create .env.example**

```
API_KEY=your-api-key-here
WEB_PASSWORD=your-web-password-here
PORT=8000
```

- [ ] **Step 3: Create app/config.py**

```python
import os

API_KEY = os.environ.get("API_KEY", "dev-key")
WEB_PASSWORD = os.environ.get("WEB_PASSWORD", "dev-pass")
PORT = int(os.environ.get("PORT", "8000"))
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "/tmp/contract-stamper")
FILE_TTL_SECONDS = 3600  # 1 hour
```

- [ ] **Step 4: Create app/__init__.py, app/api/__init__.py, app/core/__init__.py, tests/__init__.py**

All empty `__init__.py` files.

- [ ] **Step 5: Create minimal app/main.py**

```python
import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.config import UPLOAD_DIR

app = FastAPI(title="Contract Stamper", version="0.1.0")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(os.path.join(UPLOAD_DIR, "uploads"), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_DIR, "stamps"), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_DIR, "results"), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_DIR, "previews"), exist_ok=True)

static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 6: Install deps and verify server starts**

Run:
```bash
cd /Users/zeoooo/contract-stamper
pip install -r requirements.txt
python -c "from app.main import app; print('OK')"
```
Expected: `OK`

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: project scaffolding with config and FastAPI entry"
```

---

### Task 2: Authentication (API Key + Web Password)

**Files:**
- Create: `app/auth.py`
- Modify: `app/main.py`

- [ ] **Step 1: Create app/auth.py**

```python
from fastapi import Depends, HTTPException, Request, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import API_KEY, WEB_PASSWORD

bearer_scheme = HTTPBearer(auto_error=False)


async def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    if credentials is None or credentials.credentials != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return credentials.credentials


def verify_web_password(request: Request) -> bool:
    session_token = request.cookies.get("session_token")
    if session_token == WEB_PASSWORD:
        return True
    return False


def set_web_session(response: Response):
    response.set_cookie(
        key="session_token",
        value=WEB_PASSWORD,
        max_age=86400,
        httponly=True,
        samesite="lax",
    )
```

- [ ] **Step 2: Add login endpoint and page route to app/main.py**

Add after the existing code in `app/main.py`:

```python
from fastapi import Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from app.auth import verify_web_password, set_web_session
from app.config import WEB_PASSWORD


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "authenticated": verify_web_password(request),
    })


@app.post("/login")
async def login(password: str = Form(...)):
    if password != WEB_PASSWORD:
        return RedirectResponse(url="/?error=1", status_code=303)
    response = RedirectResponse(url="/", status_code=303)
    set_web_session(response)
    return response
```

- [ ] **Step 3: Create placeholder index.html for testing**

Create `app/templates/index.html`:

```html
<!DOCTYPE html>
<html><head><title>Contract Stamper</title></head>
<body>
{% if authenticated %}
<h1>Contract Stamper</h1>
{% else %}
<h1>Login Required</h1>
<form method="POST" action="/login">
  <input type="password" name="password" placeholder="Password">
  <button type="submit">Login</button>
</form>
{% endif %}
</body>
</html>
```

- [ ] **Step 4: Verify auth works**

Run:
```bash
python -c "
from fastapi.testclient import TestClient
from app.main import app
c = TestClient(app)
r = c.get('/')
assert 'Login Required' in r.text
r = c.post('/login', data={'password': 'dev-pass'})
assert r.status_code == 200
print('Auth OK')
"
```
Expected: `Auth OK`

- [ ] **Step 5: Commit**

```bash
git add app/auth.py app/main.py app/templates/index.html
git commit -m "feat: add API key + web password authentication"
```

---

### Task 3: PDF Upload + Preview Generation

**Files:**
- Create: `app/api/upload.py`, `app/core/pdf_processor.py`, `tests/conftest.py`, `tests/test_detect.py`
- Modify: `app/main.py`

- [ ] **Step 1: Create tests/conftest.py with fixtures**

```python
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
```

- [ ] **Step 2: Create app/core/pdf_processor.py**

```python
import os
import fitz
from app.config import UPLOAD_DIR


def get_page_count(pdf_path: str) -> int:
    doc = fitz.open(pdf_path)
    count = len(doc)
    doc.close()
    return count


def render_page_preview(pdf_path: str, page_num: int, dpi: int = 150) -> str:
    """Render a single page to PNG, return the output path."""
    doc = fitz.open(pdf_path)
    page = doc[page_num]
    pix = page.get_pixmap(dpi=dpi)
    preview_dir = os.path.join(UPLOAD_DIR, "previews")
    os.makedirs(preview_dir, exist_ok=True)
    filename = f"{os.path.basename(pdf_path)}_{page_num}.png"
    out_path = os.path.join(preview_dir, filename)
    pix.save(out_path)
    doc.close()
    return out_path


def render_all_previews(pdf_path: str, dpi: int = 150) -> list[str]:
    """Render all pages to PNG previews."""
    count = get_page_count(pdf_path)
    return [render_page_preview(pdf_path, i, dpi) for i in range(count)]
```

- [ ] **Step 3: Write test for PDF preview rendering**

In `tests/test_detect.py`:

```python
import os
from app.core.pdf_processor import get_page_count, render_page_preview


def test_get_page_count(sample_pdf):
    assert get_page_count(sample_pdf) == 3


def test_render_page_preview(sample_pdf, tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.pdf_processor.UPLOAD_DIR", str(tmp_path))
    path = render_page_preview(sample_pdf, 0)
    assert os.path.exists(path)
    assert path.endswith(".png")
```

- [ ] **Step 4: Run tests**

Run: `cd /Users/zeoooo/contract-stamper && python -m pytest tests/test_detect.py -v`
Expected: 2 tests PASS

- [ ] **Step 5: Create app/api/upload.py**

```python
import os
import uuid
import shutil
from fastapi import APIRouter, UploadFile, File, Depends
from app.auth import verify_api_key
from app.config import UPLOAD_DIR
from app.core.pdf_processor import get_page_count, render_all_previews

router = APIRouter(prefix="/api/v1")


@router.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    _: str = Depends(verify_api_key),
):
    file_id = uuid.uuid4().hex[:12]
    upload_dir = os.path.join(UPLOAD_DIR, "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{file_id}.pdf")

    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    page_count = get_page_count(file_path)
    previews = render_all_previews(file_path)
    preview_urls = [f"/api/v1/preview/{os.path.basename(p)}" for p in previews]

    return {
        "file_id": file_id,
        "page_count": page_count,
        "previews": preview_urls,
    }


@router.post("/upload/stamp")
async def upload_stamp(
    file: UploadFile = File(...),
    _: str = Depends(verify_api_key),
):
    stamp_id = uuid.uuid4().hex[:12]
    stamp_dir = os.path.join(UPLOAD_DIR, "stamps")
    os.makedirs(stamp_dir, exist_ok=True)
    stamp_path = os.path.join(stamp_dir, f"{stamp_id}.png")

    with open(stamp_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    return {"stamp_id": stamp_id}
```

- [ ] **Step 6: Add preview static serving and include router in main.py**

Add to `app/main.py`:

```python
from app.api.upload import router as upload_router

app.include_router(upload_router)

# Serve preview images
previews_dir = os.path.join(UPLOAD_DIR, "previews")
os.makedirs(previews_dir, exist_ok=True)

from fastapi.responses import FileResponse

@app.get("/api/v1/preview/{filename}")
async def serve_preview(filename: str):
    path = os.path.join(UPLOAD_DIR, "previews", filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404)
    return FileResponse(path)
```

Also add the missing import at the top: `from fastapi import Request, Form, HTTPException`

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: PDF upload, preview generation, and stamp upload endpoints"
```

---

### Task 4: Keyword Detection (Auto Seal Positioning)

**Files:**
- Create: `app/core/stamp_placer.py`, `app/api/detect.py`
- Modify: `app/main.py`, `tests/test_detect.py`

- [ ] **Step 1: Write test for keyword detection**

Add to `tests/test_detect.py`:

```python
from app.core.stamp_placer import detect_keywords


def test_detect_keywords_found(sample_pdf):
    results = detect_keywords(sample_pdf)
    assert len(results) == 1
    assert results[0]["keyword"] == "乙方（盖章）"
    assert results[0]["page"] == 2  # 0-indexed, third page
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
```

- [ ] **Step 2: Run tests to verify failure**

Run: `cd /Users/zeoooo/contract-stamper && python -m pytest tests/test_detect.py::test_detect_keywords_found -v`
Expected: FAIL (import error)

- [ ] **Step 3: Create app/core/stamp_placer.py**

```python
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
    """Search PDF for seal-placement keywords, return positions."""
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
    """Place a stamp image on a specific page at (x, y). Returns modified PDF path."""
    doc = fitz.open(pdf_path)
    page = doc[page_num]

    # Convert mm to points (1mm = 2.835pt)
    size_pt = size_mm * 2.835
    half = size_pt / 2

    # Center the stamp on the target position
    stamp_rect = fitz.Rect(x - half, y - half, x + half, y + half)
    page.insert_image(stamp_rect, filename=stamp_path, overlay=True)

    output_path = pdf_path.replace(".pdf", "_stamped.pdf")
    doc.save(output_path)
    doc.close()
    return output_path
```

- [ ] **Step 4: Run tests**

Run: `cd /Users/zeoooo/contract-stamper && python -m pytest tests/test_detect.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Create app/api/detect.py**

```python
import os
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.auth import verify_api_key
from app.config import UPLOAD_DIR
from app.core.stamp_placer import detect_keywords

router = APIRouter(prefix="/api/v1")


class DetectRequest(BaseModel):
    file_id: str


@router.post("/detect")
async def detect(
    req: DetectRequest,
    _: str = Depends(verify_api_key),
):
    pdf_path = os.path.join(UPLOAD_DIR, "uploads", f"{req.file_id}.pdf")
    if not os.path.exists(pdf_path):
        return {"error": "File not found"}, 404

    positions = detect_keywords(pdf_path)
    return {
        "found": len(positions) > 0,
        "positions": positions,
    }
```

- [ ] **Step 6: Include detect router in main.py**

Add to `app/main.py`:

```python
from app.api.detect import router as detect_router
app.include_router(detect_router)
```

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: keyword detection for auto seal positioning"
```

---

### Task 5: Stamp Placement (Party B Seal)

**Files:**
- Create: `tests/test_stamp_placer.py`
- Modify: `app/core/stamp_placer.py` (already created, test place_stamp)

- [ ] **Step 1: Write test for stamp placement**

Create `tests/test_stamp_placer.py`:

```python
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
```

- [ ] **Step 2: Run tests**

Run: `cd /Users/zeoooo/contract-stamper && python -m pytest tests/test_stamp_placer.py -v`
Expected: 2 tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_stamp_placer.py
git commit -m "test: add stamp placement tests"
```

---

### Task 6: Riding Seam Stamp (骑缝章)

**Files:**
- Create: `app/core/seam_stamp.py`, `tests/test_seam_stamp.py`

- [ ] **Step 1: Write tests for seam stamp**

Create `tests/test_seam_stamp.py`:

```python
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
    # Allow small variance from rotation offset
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
```

- [ ] **Step 2: Run tests to verify failure**

Run: `cd /Users/zeoooo/contract-stamper && python -m pytest tests/test_seam_stamp.py -v`
Expected: FAIL (import error)

- [ ] **Step 3: Create app/core/seam_stamp.py**

```python
import os
import random
import tempfile
import fitz
from PIL import Image


def slice_stamp(stamp_path: str, num_pages: int) -> list[str]:
    """Slice stamp into N vertical strips with random micro-offsets."""
    img = Image.open(stamp_path).convert("RGBA")
    width, height = img.size
    strip_width = width // num_pages

    strips = []
    tmp_dir = tempfile.mkdtemp()

    for i in range(num_pages):
        left = i * strip_width
        right = left + strip_width if i < num_pages - 1 else width
        strip = img.crop((left, 0, right, height))

        # Random micro-offset: rotation ±0.5°
        angle = random.uniform(-0.5, 0.5)
        strip = strip.rotate(angle, expand=True, fillcolor=(0, 0, 0, 0))

        strip_path = os.path.join(tmp_dir, f"strip_{i}.png")
        strip.save(strip_path)
        strips.append(strip_path)

    return strips


def place_seam_stamps(pdf_path: str, stamp_path: str) -> str:
    """Place riding seam stamp strips on right edge of each page."""
    doc = fitz.open(pdf_path)
    num_pages = len(doc)
    strips = slice_stamp(stamp_path, num_pages)

    for i in range(num_pages):
        page = doc[i]
        strip_img = Image.open(strips[i])
        s_width, s_height = strip_img.size

        # Scale strip to reasonable size (stamp ~120pt = ~42mm diameter)
        scale = 120.0 / Image.open(stamp_path).height
        display_w = s_width * scale
        display_h = s_height * scale

        # Position: right edge, vertically centered
        page_w = page.rect.width
        page_h = page.rect.height

        # Random vertical offset ±3px (in points)
        v_offset = random.uniform(-3, 3)
        # Random horizontal offset ±2px
        h_offset = random.uniform(-2, 2)

        x0 = page_w - display_w + h_offset
        y0 = (page_h - display_h) / 2 + v_offset
        x1 = page_w + h_offset
        y1 = y0 + display_h

        stamp_rect = fitz.Rect(x0, y0, x1, y1)
        page.insert_image(stamp_rect, filename=strips[i], overlay=True)

    output_path = pdf_path.replace(".pdf", "_seam.pdf")
    doc.save(output_path)
    doc.close()
    return output_path
```

- [ ] **Step 4: Run tests**

Run: `cd /Users/zeoooo/contract-stamper && python -m pytest tests/test_seam_stamp.py -v`
Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/core/seam_stamp.py tests/test_seam_stamp.py
git commit -m "feat: riding seam stamp slicing and placement"
```

---

### Task 7: Simulated Scan Effect

**Files:**
- Create: `app/core/scan_effect.py`, `tests/test_scan_effect.py`

- [ ] **Step 1: Write tests for scan effect**

Create `tests/test_scan_effect.py`:

```python
import os
from PIL import Image
from app.core.scan_effect import apply_scan_to_image, scan_params_from_slider


def test_scan_params_light():
    params = scan_params_from_slider(90)
    assert params["dpi"] == 300
    assert params["tilt_max"] <= 0.3


def test_scan_params_heavy():
    params = scan_params_from_slider(10)
    assert params["dpi"] == 150
    assert params["tilt_max"] >= 0.8


def test_apply_scan_to_image():
    # Create a white test image
    img = Image.new("RGB", (600, 800), (255, 255, 255))
    params = scan_params_from_slider(50)
    result = apply_scan_to_image(img, params)
    assert isinstance(result, Image.Image)
    assert result.size[0] > 0
    assert result.size[1] > 0


def test_scan_effect_changes_pixels():
    img = Image.new("RGB", (100, 100), (255, 255, 255))
    params = scan_params_from_slider(30)
    result = apply_scan_to_image(img, params)
    # The result should not be identical to the input (noise, tint applied)
    original_pixels = list(img.getdata())
    result_pixels = list(result.getdata())
    assert original_pixels != result_pixels
```

- [ ] **Step 2: Run tests to verify failure**

Run: `cd /Users/zeoooo/contract-stamper && python -m pytest tests/test_scan_effect.py -v`
Expected: FAIL (import error)

- [ ] **Step 3: Create app/core/scan_effect.py**

```python
import random
import numpy as np
from PIL import Image, ImageFilter, ImageDraw


def scan_params_from_slider(value: int) -> dict:
    """Map slider value (0-100) to scan effect parameters."""
    # 80-100: light, 40-80: medium, 0-40: heavy
    v = max(0, min(100, value))

    if v >= 80:
        t = (v - 80) / 20  # 0..1 within light range
        return {
            "dpi": 300,
            "tint_strength": 0.05 * (1 - t),
            "noise_amount": 3 * (1 - t),
            "tilt_max": 0.3 * (1 - t),
            "blur_radius": 0,
            "vignette_strength": 0,
        }
    elif v >= 40:
        t = (v - 40) / 40  # 0..1 within medium range
        return {
            "dpi": int(200 + 100 * t),
            "tint_strength": 0.15 - 0.1 * t,
            "noise_amount": 8 - 5 * t,
            "tilt_max": 0.8 - 0.5 * t,
            "blur_radius": 0.5 * (1 - t),
            "vignette_strength": 0.3 * (1 - t),
        }
    else:
        t = v / 40  # 0..1 within heavy range
        return {
            "dpi": int(150 + 50 * t),
            "tint_strength": 0.25 - 0.1 * t,
            "noise_amount": 15 - 7 * t,
            "tilt_max": 1.5 - 0.7 * t,
            "blur_radius": 1.0 - 0.5 * t,
            "vignette_strength": 0.6 - 0.3 * t,
        }


def _apply_paper_tint(img: Image.Image, strength: float) -> Image.Image:
    """Add warm yellow/aged paper tint."""
    tint = Image.new("RGB", img.size, (245, 235, 210))
    return Image.blend(img, tint, strength)


def _apply_noise(img: Image.Image, amount: float) -> Image.Image:
    """Add random noise grain."""
    arr = np.array(img, dtype=np.float32)
    noise = np.random.normal(0, amount, arr.shape)
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)


def _apply_tilt(img: Image.Image, max_degrees: float) -> Image.Image:
    """Rotate image slightly."""
    if max_degrees <= 0:
        return img
    angle = random.uniform(-max_degrees, max_degrees)
    return img.rotate(angle, expand=False, fillcolor=(245, 240, 230))


def _apply_vignette(img: Image.Image, strength: float) -> Image.Image:
    """Add edge darkening (scanner shadow effect)."""
    if strength <= 0:
        return img
    w, h = img.size
    vignette = Image.new("L", (w, h), 255)
    draw = ImageDraw.Draw(vignette)

    border = int(min(w, h) * 0.1)
    for i in range(border):
        alpha = int(255 * (1 - strength * (1 - i / border)))
        draw.rectangle([i, i, w - 1 - i, h - 1 - i], outline=alpha)

    result = img.copy()
    result.putalpha(255)
    vignette_rgba = Image.merge("RGBA", (*img.split(), vignette))
    # Composite onto slightly dark background
    bg = Image.new("RGB", (w, h), (220, 215, 200))
    bg.paste(vignette_rgba, mask=vignette_rgba.split()[3])
    return bg


def apply_scan_to_image(img: Image.Image, params: dict) -> Image.Image:
    """Apply all scan effects to a single image."""
    result = img.convert("RGB")
    result = _apply_paper_tint(result, params["tint_strength"])
    result = _apply_noise(result, params["noise_amount"])
    result = _apply_tilt(result, params["tilt_max"])
    if params["blur_radius"] > 0:
        result = result.filter(ImageFilter.GaussianBlur(radius=params["blur_radius"]))
    result = _apply_vignette(result, params["vignette_strength"])
    return result
```

- [ ] **Step 4: Run tests**

Run: `cd /Users/zeoooo/contract-stamper && python -m pytest tests/test_scan_effect.py -v`
Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/core/scan_effect.py tests/test_scan_effect.py
git commit -m "feat: simulated scan effect with configurable quality slider"
```

---

### Task 8: Stamp Processing API (Async Task)

**Files:**
- Create: `app/api/stamp.py`, `app/api/result.py`
- Modify: `app/main.py`

- [ ] **Step 1: Create app/api/stamp.py**

```python
import os
import uuid
import json
import threading
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.auth import verify_api_key
from app.config import UPLOAD_DIR
from app.core.stamp_placer import place_stamp
from app.core.seam_stamp import place_seam_stamps
from app.core.scan_effect import scan_params_from_slider, apply_scan_to_image
from app.core.pdf_processor import get_page_count
import fitz
from PIL import Image

router = APIRouter(prefix="/api/v1")

# In-memory task store
tasks: dict[str, dict] = {}


class Position(BaseModel):
    page: int
    x: float
    y: float


class StampRequest(BaseModel):
    file_id: str
    stamp_id: str
    party_b_position: Position | None = None
    riding_seam: bool = True
    scan_effect: int = 0  # 0 = no effect


def _process_stamp(task_id: str, req: StampRequest):
    try:
        tasks[task_id]["status"] = "processing"

        pdf_path = os.path.join(UPLOAD_DIR, "uploads", f"{req.file_id}.pdf")
        stamp_path = os.path.join(UPLOAD_DIR, "stamps", f"{req.stamp_id}.png")
        current_pdf = pdf_path

        # Step 1: Place party B stamp if position given
        if req.party_b_position:
            current_pdf = place_stamp(
                current_pdf, stamp_path,
                page_num=req.party_b_position.page,
                x=req.party_b_position.x,
                y=req.party_b_position.y,
            )
            tasks[task_id]["progress"] = 30

        # Step 2: Place riding seam stamps
        if req.riding_seam:
            current_pdf = place_seam_stamps(current_pdf, stamp_path)
            tasks[task_id]["progress"] = 60

        # Step 3: Apply scan effect
        if req.scan_effect > 0:
            params = scan_params_from_slider(req.scan_effect)
            doc = fitz.open(current_pdf)
            processed_images = []

            for page_num in range(len(doc)):
                page = doc[page_num]
                pix = page.get_pixmap(dpi=params["dpi"])
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                processed = apply_scan_to_image(img, params)
                processed_images.append(processed)

            doc.close()

            # Reassemble into PDF
            result_doc = fitz.open()
            for img in processed_images:
                img_bytes = img.tobytes("jpeg", "RGB")
                # Save temp image
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                    img.save(tmp.name, "JPEG", quality=95)
                    img_doc = fitz.open(tmp.name)
                    rect = img_doc[0].rect
                    pdf_bytes = img_doc.convert_to_pdf()
                    img_doc.close()
                    img_pdf = fitz.open("pdf", pdf_bytes)
                    result_doc.insert_pdf(img_pdf)
                    os.unlink(tmp.name)

            current_pdf = os.path.join(UPLOAD_DIR, "results", f"{task_id}.pdf")
            result_doc.save(current_pdf)
            result_doc.close()
        else:
            # Copy to results dir
            import shutil
            result_path = os.path.join(UPLOAD_DIR, "results", f"{task_id}.pdf")
            shutil.copy2(current_pdf, result_path)
            current_pdf = result_path

        tasks[task_id]["status"] = "completed"
        tasks[task_id]["progress"] = 100
        tasks[task_id]["result_path"] = current_pdf

    except Exception as e:
        tasks[task_id]["status"] = "error"
        tasks[task_id]["error"] = str(e)


@router.post("/stamp")
async def stamp(
    req: StampRequest,
    _: str = Depends(verify_api_key),
):
    task_id = uuid.uuid4().hex[:12]
    tasks[task_id] = {"status": "pending", "progress": 0}

    thread = threading.Thread(target=_process_stamp, args=(task_id, req))
    thread.start()

    return {"task_id": task_id}
```

- [ ] **Step 2: Create app/api/result.py**

```python
import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from app.auth import verify_api_key
from app.api.stamp import tasks

router = APIRouter(prefix="/api/v1")


@router.get("/result/{task_id}")
async def get_result(
    task_id: str,
    _: str = Depends(verify_api_key),
):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    task = tasks[task_id]
    return {
        "task_id": task_id,
        "status": task["status"],
        "progress": task.get("progress", 0),
        "error": task.get("error"),
    }


@router.get("/download/{task_id}")
async def download(
    task_id: str,
    _: str = Depends(verify_api_key),
):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    task = tasks[task_id]
    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail="Task not completed")

    result_path = task["result_path"]
    if not os.path.exists(result_path):
        raise HTTPException(status_code=404, detail="Result file not found")

    return FileResponse(
        result_path,
        media_type="application/pdf",
        filename=f"stamped_{task_id}.pdf",
    )
```

- [ ] **Step 3: Include routers in main.py**

Add to `app/main.py`:

```python
from app.api.stamp import router as stamp_router
from app.api.result import router as result_router
app.include_router(stamp_router)
app.include_router(result_router)
```

- [ ] **Step 4: Verify server starts with all routes**

Run:
```bash
python -c "
from fastapi.testclient import TestClient
from app.main import app
c = TestClient(app)
r = c.get('/health')
assert r.json() == {'status': 'ok'}
print('All routes loaded OK')
"
```
Expected: `All routes loaded OK`

- [ ] **Step 5: Commit**

```bash
git add app/api/stamp.py app/api/result.py app/main.py
git commit -m "feat: async stamp processing API with result polling and download"
```

---

### Task 9: Web Frontend - HTML Structure

**Files:**
- Create: `app/templates/index.html`

- [ ] **Step 1: Write the full index.html**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Contract Stamper</title>
    <link rel="stylesheet" href="/static/css/style.css">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js"></script>
    <script>pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';</script>
</head>
<body>
    <!-- Login overlay -->
    {% if not authenticated %}
    <div class="login-overlay" id="loginOverlay">
        <div class="login-card">
            <h2>Contract Stamper</h2>
            <p class="login-subtitle">请输入访问密码</p>
            <form method="POST" action="/login" class="login-form">
                <input type="password" name="password" placeholder="密码" class="input-field" autofocus>
                <button type="submit" class="btn-primary">进入</button>
            </form>
            {% if request.query_params.get('error') %}
            <p class="error-text">密码错误</p>
            {% endif %}
        </div>
    </div>
    {% endif %}

    {% if authenticated %}
    <header class="app-header">
        <h1>Contract Stamper</h1>
        <span class="header-subtitle">合同自动盖章工具</span>
    </header>

    <main class="app-main">
        <!-- Left panel: Controls -->
        <aside class="control-panel">
            <!-- Upload PDF -->
            <section class="panel-section">
                <label class="section-label">合同文件</label>
                <div class="upload-zone" id="pdfUploadZone">
                    <input type="file" id="pdfInput" accept=".pdf" hidden>
                    <div class="upload-placeholder" id="pdfPlaceholder">
                        <span class="upload-icon">&#128196;</span>
                        <span>拖拽或点击上传 PDF</span>
                    </div>
                    <div class="upload-done" id="pdfDone" hidden>
                        <span class="file-name" id="pdfFileName"></span>
                        <button class="btn-text" id="pdfClear">更换</button>
                    </div>
                </div>
            </section>

            <!-- Upload Stamp -->
            <section class="panel-section">
                <label class="section-label">印章图片</label>
                <div class="upload-zone" id="stampUploadZone">
                    <input type="file" id="stampInput" accept=".png" hidden>
                    <div class="upload-placeholder" id="stampPlaceholder">
                        <span class="upload-icon">&#128308;</span>
                        <span>拖拽或点击上传印章 PNG</span>
                    </div>
                    <div class="upload-done" id="stampDone" hidden>
                        <img id="stampPreview" class="stamp-preview" alt="stamp">
                        <button class="btn-text" id="stampClear">更换</button>
                    </div>
                </div>
            </section>

            <!-- Stamp Settings -->
            <section class="panel-section">
                <label class="section-label">盖章设置</label>
                <div class="setting-row">
                    <span>印章大小</span>
                    <input type="range" id="stampSize" min="20" max="60" value="42" class="slider">
                    <span id="stampSizeVal">42mm</span>
                </div>
                <div class="setting-row">
                    <span>骑缝章</span>
                    <label class="toggle">
                        <input type="checkbox" id="seamToggle" checked>
                        <span class="toggle-slider"></span>
                    </label>
                </div>
            </section>

            <!-- Scan Effect -->
            <section class="panel-section">
                <label class="section-label">扫描效果</label>
                <div class="setting-row">
                    <span>效果强度</span>
                    <input type="range" id="scanSlider" min="0" max="100" value="0" class="slider">
                    <span id="scanVal">关闭</span>
                </div>
            </section>

            <!-- Action -->
            <section class="panel-section">
                <button class="btn-primary btn-process" id="processBtn" disabled>
                    <span class="btn-text-inner">开始处理</span>
                    <div class="btn-progress" id="btnProgress"></div>
                </button>
                <button class="btn-secondary" id="downloadBtn" hidden>下载结果 PDF</button>
            </section>

            <!-- Status -->
            <div class="status-bar" id="statusBar" hidden>
                <span id="statusText"></span>
            </div>
        </aside>

        <!-- Right panel: PDF Preview -->
        <section class="preview-panel">
            <div class="preview-header">
                <span id="previewTitle">上传合同以预览</span>
                <div class="preview-nav" id="previewNav" hidden>
                    <button class="btn-icon" id="prevPage">&lt;</button>
                    <span id="pageInfo">1 / 1</span>
                    <button class="btn-icon" id="nextPage">&gt;</button>
                </div>
            </div>
            <div class="preview-canvas-wrap" id="canvasWrap">
                <canvas id="pdfCanvas"></canvas>
                <!-- Stamp position indicator (draggable) -->
                <div class="stamp-marker" id="stampMarker" hidden>
                    <div class="stamp-marker-ring"></div>
                </div>
            </div>
        </section>
    </main>
    {% endif %}

    {% if authenticated %}
    <script src="/static/js/app.js"></script>
    {% endif %}
</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add app/templates/index.html
git commit -m "feat: web frontend HTML structure with all UI components"
```

---

### Task 10: Web Frontend - CSS Styling

**Files:**
- Create: `app/static/css/style.css`

- [ ] **Step 1: Write style.css with end_to_end-layout aesthetic**

```css
:root {
    --green: #407600;
    --green-dark: #356200;
    --green-light: #f4f9ed;
    --green-border: #c5e0a5;
    --dark: #1a1a1a;
    --gray: #666;
    --gray-light: #f7f7f7;
    --border: #e5e5e5;
    --bg: #f0f2f5;
    --card: #fff;
    --radius-sm: 8px;
    --radius-md: 12px;
    --radius-lg: 16px;
    --shadow-card: 0 1px 4px rgba(0,0,0,.06);
    --shadow-modal: 0 8px 32px rgba(0,0,0,.12);
    --font: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'PingFang SC', sans-serif;
    --font-mono: 'SF Mono', Monaco, Consolas, monospace;
    --transition: .2s ease;
}

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
    font-family: var(--font);
    background: var(--bg);
    color: var(--dark);
    min-height: 100vh;
}

/* ── Login ── */
.login-overlay {
    position: fixed; inset: 0;
    background: rgba(0,0,0,.35);
    backdrop-filter: blur(4px);
    display: flex; align-items: center; justify-content: center;
    z-index: 1000;
}

.login-card {
    background: var(--card);
    border-radius: var(--radius-lg);
    padding: 48px 40px;
    box-shadow: var(--shadow-modal);
    text-align: center;
    width: 360px;
    animation: scaleIn .25s ease;
}

@keyframes scaleIn {
    from { opacity: 0; transform: scale(.9); }
    to { opacity: 1; transform: scale(1); }
}

.login-card h2 {
    font-size: 24px;
    font-weight: 700;
    margin-bottom: 4px;
    color: var(--green);
}

.login-subtitle {
    color: var(--gray);
    font-size: 14px;
    margin-bottom: 28px;
}

.login-form {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.input-field {
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: 12px 14px;
    font-size: 15px;
    font-family: var(--font);
    outline: none;
    transition: border var(--transition), box-shadow var(--transition);
}

.input-field:focus {
    border-color: var(--green);
    box-shadow: 0 0 0 3px rgba(64,118,0,.1);
}

.error-text {
    color: #d32;
    font-size: 13px;
    margin-top: 12px;
}

/* ── Buttons ── */
.btn-primary {
    background: linear-gradient(135deg, var(--green), var(--green-dark));
    color: #fff;
    border: none;
    border-radius: var(--radius-sm);
    padding: 12px 24px;
    font-size: 15px;
    font-weight: 600;
    cursor: pointer;
    transition: opacity var(--transition), box-shadow var(--transition);
    position: relative;
    overflow: hidden;
    font-family: var(--font);
}

.btn-primary:hover:not(:disabled) {
    opacity: .9;
    box-shadow: 0 2px 8px rgba(64,118,0,.25);
}

.btn-primary:disabled {
    opacity: .5;
    cursor: not-allowed;
}

.btn-process {
    width: 100%;
    padding: 14px;
    font-size: 16px;
}

.btn-progress {
    position: absolute;
    left: 0; top: 0; bottom: 0;
    width: 0;
    background: rgba(255,255,255,.2);
    transition: width .3s ease;
}

.btn-secondary {
    width: 100%;
    padding: 12px;
    background: var(--green-light);
    color: var(--green);
    border: 1px solid var(--green-border);
    border-radius: var(--radius-sm);
    font-size: 15px;
    font-weight: 600;
    cursor: pointer;
    transition: background var(--transition);
    font-family: var(--font);
    margin-top: 8px;
}

.btn-secondary:hover {
    background: var(--green-border);
}

.btn-text {
    background: none;
    border: none;
    color: var(--green);
    font-size: 13px;
    cursor: pointer;
    font-family: var(--font);
    text-decoration: underline;
}

.btn-icon {
    background: var(--gray-light);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    width: 32px; height: 32px;
    display: flex; align-items: center; justify-content: center;
    cursor: pointer;
    font-size: 14px;
    transition: background var(--transition);
    font-family: var(--font);
}

.btn-icon:hover {
    background: var(--border);
}

/* ── Header ── */
.app-header {
    background: linear-gradient(135deg, var(--green), var(--green-dark));
    color: #fff;
    padding: 16px 24px;
    display: flex;
    align-items: baseline;
    gap: 12px;
}

.app-header h1 {
    font-size: 20px;
    font-weight: 700;
}

.header-subtitle {
    font-size: 13px;
    opacity: .8;
}

/* ── Main Layout ── */
.app-main {
    display: flex;
    gap: 0;
    height: calc(100vh - 56px);
}

/* ── Control Panel ── */
.control-panel {
    width: 340px;
    min-width: 340px;
    background: var(--card);
    border-right: 1px solid var(--border);
    padding: 20px;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 20px;
}

.panel-section {
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.section-label {
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: .5px;
    color: var(--gray);
}

/* ── Upload Zone ── */
.upload-zone {
    border: 2px dashed var(--border);
    border-radius: var(--radius-md);
    padding: 20px;
    text-align: center;
    cursor: pointer;
    transition: border-color var(--transition), background var(--transition);
}

.upload-zone:hover,
.upload-zone.dragover {
    border-color: var(--green-border);
    background: var(--green-light);
}

.upload-placeholder {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    color: var(--gray);
    font-size: 14px;
}

.upload-icon {
    font-size: 28px;
}

.upload-done {
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.file-name {
    font-size: 14px;
    font-weight: 500;
    color: var(--dark);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 200px;
}

.stamp-preview {
    width: 48px;
    height: 48px;
    object-fit: contain;
    border-radius: 4px;
}

/* ── Settings ── */
.setting-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    font-size: 14px;
}

.slider {
    flex: 1;
    max-width: 140px;
    accent-color: var(--green);
}

/* ── Toggle Switch ── */
.toggle {
    position: relative;
    width: 44px; height: 24px;
    display: inline-block;
}

.toggle input { display: none; }

.toggle-slider {
    position: absolute; inset: 0;
    background: var(--border);
    border-radius: 12px;
    cursor: pointer;
    transition: background var(--transition);
}

.toggle-slider::after {
    content: '';
    position: absolute;
    left: 2px; top: 2px;
    width: 20px; height: 20px;
    background: #fff;
    border-radius: 50%;
    transition: transform var(--transition);
    box-shadow: 0 1px 3px rgba(0,0,0,.15);
}

.toggle input:checked + .toggle-slider {
    background: var(--green);
}

.toggle input:checked + .toggle-slider::after {
    transform: translateX(20px);
}

/* ── Status Bar ── */
.status-bar {
    padding: 10px 14px;
    border-radius: var(--radius-sm);
    font-size: 13px;
    font-family: var(--font-mono);
}

.status-bar.loading { background: #eff6ff; color: #1d4ed8; }
.status-bar.success { background: var(--green-light); color: var(--green); }
.status-bar.error { background: #fef2f2; color: #d32; }

/* ── Preview Panel ── */
.preview-panel {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
}

.preview-header {
    padding: 12px 20px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 1px solid var(--border);
    background: var(--card);
    font-size: 14px;
    color: var(--gray);
}

.preview-nav {
    display: flex;
    align-items: center;
    gap: 8px;
}

#pageInfo {
    font-size: 13px;
    font-family: var(--font-mono);
    min-width: 50px;
    text-align: center;
}

.preview-canvas-wrap {
    flex: 1;
    overflow: auto;
    display: flex;
    align-items: flex-start;
    justify-content: center;
    padding: 24px;
    position: relative;
}

#pdfCanvas {
    box-shadow: var(--shadow-card);
    border-radius: 2px;
    max-width: 100%;
}

/* ── Stamp Marker ── */
.stamp-marker {
    position: absolute;
    cursor: move;
    z-index: 10;
}

.stamp-marker-ring {
    width: 80px;
    height: 80px;
    border: 2px dashed var(--green);
    border-radius: 50%;
    background: rgba(64,118,0,.08);
    animation: pulse 2s ease infinite;
}

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: .5; }
}

/* ── Mobile ── */
@media (max-width: 768px) {
    .app-main {
        flex-direction: column-reverse;
        height: auto;
    }

    .control-panel {
        width: 100%;
        min-width: unset;
        border-right: none;
        border-top: 1px solid var(--border);
        max-height: 50vh;
    }

    .login-card {
        margin: 0 16px;
        border-radius: 20px 20px 0 0;
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        width: auto;
        animation: slideUp .3s ease;
    }

    @keyframes slideUp {
        from { transform: translateY(100%); }
        to { transform: translateY(0); }
    }
}
```

- [ ] **Step 2: Commit**

```bash
git add app/static/css/style.css
git commit -m "feat: web frontend CSS with organic green theme"
```

---

### Task 11: Web Frontend - JavaScript Interaction

**Files:**
- Create: `app/static/js/app.js`

- [ ] **Step 1: Write app.js**

```javascript
(function () {
    'use strict';

    // ── State ──
    let fileId = null;
    let stampId = null;
    let pdfDoc = null;
    let currentPage = 0;
    let totalPages = 0;
    let detectedPosition = null;
    let manualPosition = null;
    let resultTaskId = null;

    // ── Elements ──
    const pdfInput = document.getElementById('pdfInput');
    const pdfUploadZone = document.getElementById('pdfUploadZone');
    const pdfPlaceholder = document.getElementById('pdfPlaceholder');
    const pdfDone = document.getElementById('pdfDone');
    const pdfFileName = document.getElementById('pdfFileName');
    const pdfClear = document.getElementById('pdfClear');

    const stampInput = document.getElementById('stampInput');
    const stampUploadZone = document.getElementById('stampUploadZone');
    const stampPlaceholder = document.getElementById('stampPlaceholder');
    const stampDone = document.getElementById('stampDone');
    const stampPreview = document.getElementById('stampPreview');
    const stampClear = document.getElementById('stampClear');

    const stampSize = document.getElementById('stampSize');
    const stampSizeVal = document.getElementById('stampSizeVal');
    const seamToggle = document.getElementById('seamToggle');
    const scanSlider = document.getElementById('scanSlider');
    const scanVal = document.getElementById('scanVal');

    const processBtn = document.getElementById('processBtn');
    const btnProgress = document.getElementById('btnProgress');
    const downloadBtn = document.getElementById('downloadBtn');
    const statusBar = document.getElementById('statusBar');
    const statusText = document.getElementById('statusText');

    const canvas = document.getElementById('pdfCanvas');
    const canvasWrap = document.getElementById('canvasWrap');
    const previewTitle = document.getElementById('previewTitle');
    const previewNav = document.getElementById('previewNav');
    const prevPage = document.getElementById('prevPage');
    const nextPage = document.getElementById('nextPage');
    const pageInfo = document.getElementById('pageInfo');
    const stampMarker = document.getElementById('stampMarker');

    // ── API helper ──
    function getSessionCookie() {
        return document.cookie.split(';').find(c => c.trim().startsWith('session_token='));
    }

    async function api(method, path, body, isFormData) {
        const opts = { method };
        if (isFormData) {
            opts.body = body;
        } else if (body) {
            opts.headers = { 'Content-Type': 'application/json' };
            opts.body = JSON.stringify(body);
        }
        // Web session uses cookie auth; add API key header if available
        const resp = await fetch(path, opts);
        return resp;
    }

    // For web usage, we use cookie-based auth. Add API key bypass for web.
    // We'll modify the backend to allow cookie OR api key auth.

    // ── Upload handlers ──
    function setupUploadZone(zone, input, onFile) {
        zone.addEventListener('click', () => input.click());
        zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('dragover'); });
        zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
        zone.addEventListener('drop', e => {
            e.preventDefault();
            zone.classList.remove('dragover');
            if (e.dataTransfer.files.length) onFile(e.dataTransfer.files[0]);
        });
        input.addEventListener('change', () => {
            if (input.files.length) onFile(input.files[0]);
        });
    }

    async function uploadPdf(file) {
        showStatus('loading', '上传合同中...');
        const fd = new FormData();
        fd.append('file', file);
        const resp = await api('POST', '/api/v1/upload', fd, true);
        if (!resp.ok) { showStatus('error', '上传失败'); return; }
        const data = await resp.json();
        fileId = data.file_id;
        totalPages = data.page_count;
        pdfPlaceholder.hidden = true;
        pdfDone.hidden = false;
        pdfFileName.textContent = file.name;

        // Load PDF for preview
        const pdfData = await file.arrayBuffer();
        pdfDoc = await pdfjsLib.getDocument({ data: pdfData }).promise;
        currentPage = 0;
        renderPage(0);
        previewNav.hidden = false;

        // Auto-detect
        await detectKeywords();
        checkReady();
        hideStatus();
    }

    async function uploadStamp(file) {
        showStatus('loading', '上传印章中...');
        const fd = new FormData();
        fd.append('file', file);
        const resp = await api('POST', '/api/v1/upload/stamp', fd, true);
        if (!resp.ok) { showStatus('error', '上传失败'); return; }
        const data = await resp.json();
        stampId = data.stamp_id;
        stampPlaceholder.hidden = true;
        stampDone.hidden = false;
        stampPreview.src = URL.createObjectURL(file);
        checkReady();
        hideStatus();
    }

    setupUploadZone(pdfUploadZone, pdfInput, uploadPdf);
    setupUploadZone(stampUploadZone, stampInput, uploadStamp);

    pdfClear.addEventListener('click', e => {
        e.stopPropagation();
        fileId = null; pdfDoc = null; detectedPosition = null; manualPosition = null;
        pdfPlaceholder.hidden = false; pdfDone.hidden = true;
        previewNav.hidden = true;
        canvas.getContext('2d').clearRect(0, 0, canvas.width, canvas.height);
        previewTitle.textContent = '上传合同以预览';
        stampMarker.hidden = true;
        checkReady();
    });

    stampClear.addEventListener('click', e => {
        e.stopPropagation();
        stampId = null;
        stampPlaceholder.hidden = false; stampDone.hidden = true;
        checkReady();
    });

    // ── PDF rendering ──
    async function renderPage(num) {
        const page = await pdfDoc.getPage(num + 1);
        const scale = (canvasWrap.clientWidth - 48) / page.getViewport({ scale: 1 }).width;
        const viewport = page.getViewport({ scale: Math.min(scale, 2) });

        canvas.width = viewport.width;
        canvas.height = viewport.height;
        const ctx = canvas.getContext('2d');
        await page.render({ canvasContext: ctx, viewport }).promise;

        currentPage = num;
        pageInfo.textContent = `${num + 1} / ${totalPages}`;
        previewTitle.textContent = '合同预览';

        // Show stamp marker if detected on this page
        updateStampMarker(viewport);
    }

    prevPage.addEventListener('click', () => {
        if (currentPage > 0) renderPage(currentPage - 1);
    });
    nextPage.addEventListener('click', () => {
        if (currentPage < totalPages - 1) renderPage(currentPage + 1);
    });

    // ── Keyword detection ──
    async function detectKeywords() {
        const resp = await api('POST', '/api/v1/detect', { file_id: fileId });
        const data = await resp.json();
        if (data.found && data.positions.length > 0) {
            detectedPosition = data.positions[0];
            showStatus('success', `已识别: "${detectedPosition.keyword}" 在第 ${detectedPosition.page + 1} 页`);
            // Navigate to detected page
            renderPage(detectedPosition.page);
        } else {
            showStatus('loading', '未识别到盖章位置，请在预览中点击指定');
            enableManualClick();
        }
    }

    // ── Manual click positioning ──
    function enableManualClick() {
        canvasWrap.style.cursor = 'crosshair';
        canvasWrap.addEventListener('click', onCanvasClick);
    }

    function onCanvasClick(e) {
        const rect = canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        // Convert to PDF coordinates
        const scaleX = canvas.width / rect.width;
        const scaleY = canvas.height / rect.height;

        manualPosition = {
            page: currentPage,
            x: x * scaleX,
            y: y * scaleY,
            canvasX: x,
            canvasY: y,
        };

        stampMarker.hidden = false;
        stampMarker.style.left = (rect.left - canvasWrap.getBoundingClientRect().left + x - 40) + 'px';
        stampMarker.style.top = (rect.top - canvasWrap.getBoundingClientRect().top + y - 40) + 'px';

        showStatus('success', `已指定盖章位置: 第 ${currentPage + 1} 页`);
        canvasWrap.style.cursor = 'default';
        canvasWrap.removeEventListener('click', onCanvasClick);
        checkReady();
    }

    function updateStampMarker(viewport) {
        const pos = detectedPosition;
        if (!pos || pos.page !== currentPage) {
            stampMarker.hidden = true;
            return;
        }
        stampMarker.hidden = false;
        const rect = canvas.getBoundingClientRect();
        const wrapRect = canvasWrap.getBoundingClientRect();
        const scaleX = rect.width / viewport.width;
        const scaleY = rect.height / viewport.height;
        const cx = pos.x * scaleX;
        const cy = pos.y * scaleY;
        stampMarker.style.left = (rect.left - wrapRect.left + cx - 40) + 'px';
        stampMarker.style.top = (rect.top - wrapRect.top + cy - 40) + 'px';
    }

    // Make stamp marker draggable
    let dragging = false, dragStartX, dragStartY, markerStartX, markerStartY;
    stampMarker.addEventListener('mousedown', e => {
        dragging = true;
        dragStartX = e.clientX;
        dragStartY = e.clientY;
        markerStartX = stampMarker.offsetLeft;
        markerStartY = stampMarker.offsetTop;
        e.preventDefault();
    });
    document.addEventListener('mousemove', e => {
        if (!dragging) return;
        stampMarker.style.left = (markerStartX + e.clientX - dragStartX) + 'px';
        stampMarker.style.top = (markerStartY + e.clientY - dragStartY) + 'px';
    });
    document.addEventListener('mouseup', () => {
        if (!dragging) return;
        dragging = false;
        // Update position based on marker center relative to canvas
        const rect = canvas.getBoundingClientRect();
        const wrapRect = canvasWrap.getBoundingClientRect();
        const cx = stampMarker.offsetLeft + 40 - (rect.left - wrapRect.left);
        const cy = stampMarker.offsetTop + 40 - (rect.top - wrapRect.top);
        const scaleX = canvas.width / rect.width;
        const scaleY = canvas.height / rect.height;
        if (detectedPosition && detectedPosition.page === currentPage) {
            detectedPosition.x = cx * scaleX;
            detectedPosition.y = cy * scaleY;
        } else {
            manualPosition = { page: currentPage, x: cx * scaleX, y: cy * scaleY };
        }
    });

    // ── Settings ──
    stampSize.addEventListener('input', () => {
        stampSizeVal.textContent = stampSize.value + 'mm';
    });

    scanSlider.addEventListener('input', () => {
        const v = parseInt(scanSlider.value);
        if (v === 0) scanVal.textContent = '关闭';
        else if (v >= 80) scanVal.textContent = '轻度';
        else if (v >= 40) scanVal.textContent = '中度';
        else scanVal.textContent = '重度';
    });

    // ── Process ──
    function checkReady() {
        processBtn.disabled = !(fileId && stampId && (detectedPosition || manualPosition));
    }

    processBtn.addEventListener('click', async () => {
        processBtn.disabled = true;
        downloadBtn.hidden = true;
        showStatus('loading', '处理中...');

        const pos = detectedPosition || manualPosition;
        // Convert canvas coordinates to PDF page coordinates
        // We need to get the actual PDF page dimensions
        const page = await pdfDoc.getPage(pos.page + 1);
        const viewport = page.getViewport({ scale: 1 });
        const displayScale = canvas.width / viewport.width;

        const pdfX = pos.x / displayScale;
        const pdfY = pos.y / displayScale;

        const body = {
            file_id: fileId,
            stamp_id: stampId,
            party_b_position: { page: pos.page, x: pdfX, y: pdfY },
            riding_seam: seamToggle.checked,
            scan_effect: parseInt(scanSlider.value),
        };

        const resp = await api('POST', '/api/v1/stamp', body);
        const data = await resp.json();
        resultTaskId = data.task_id;
        pollResult(resultTaskId);
    });

    async function pollResult(taskId) {
        const resp = await api('GET', `/api/v1/result/${taskId}`);
        const data = await resp.json();

        if (data.status === 'completed') {
            btnProgress.style.width = '100%';
            showStatus('success', '处理完成');
            downloadBtn.hidden = false;
            processBtn.disabled = false;
            setTimeout(() => { btnProgress.style.width = '0'; }, 500);
        } else if (data.status === 'error') {
            showStatus('error', '处理失败: ' + (data.error || '未知错误'));
            processBtn.disabled = false;
            btnProgress.style.width = '0';
        } else {
            btnProgress.style.width = (data.progress || 0) + '%';
            setTimeout(() => pollResult(taskId), 800);
        }
    }

    downloadBtn.addEventListener('click', () => {
        if (resultTaskId) {
            window.location.href = `/api/v1/download/${resultTaskId}`;
        }
    });

    // ── Status ──
    function showStatus(type, msg) {
        statusBar.hidden = false;
        statusBar.className = 'status-bar ' + type;
        statusText.textContent = msg;
    }

    function hideStatus() {
        setTimeout(() => { statusBar.hidden = true; }, 3000);
    }
})();
```

- [ ] **Step 2: Commit**

```bash
git add app/static/js/app.js
git commit -m "feat: web frontend JavaScript with upload, preview, and stamp interaction"
```

---

### Task 12: Backend Auth Fix - Allow Cookie OR API Key

**Files:**
- Modify: `app/auth.py`, `app/api/upload.py`, `app/api/detect.py`

The web frontend uses cookie auth, but API endpoints currently require API key. We need endpoints to accept either.

- [ ] **Step 1: Update app/auth.py to support dual auth**

Add to `app/auth.py`:

```python
async def verify_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    """Accept either API key (Bearer token) or web session cookie."""
    # Check API key first
    if credentials and credentials.credentials == API_KEY:
        return True
    # Fall back to cookie session
    if verify_web_password(request):
        return True
    raise HTTPException(status_code=401, detail="Authentication required")
```

- [ ] **Step 2: Replace verify_api_key with verify_auth in all API routers**

In `app/api/upload.py`, `app/api/detect.py`, `app/api/stamp.py`, `app/api/result.py`:

Replace:
```python
from app.auth import verify_api_key
```
with:
```python
from app.auth import verify_auth
```

And change all `Depends(verify_api_key)` to `Depends(verify_auth)`.

- [ ] **Step 3: Verify server starts**

Run:
```bash
python -c "from app.main import app; print('OK')"
```
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add app/auth.py app/api/upload.py app/api/detect.py app/api/stamp.py app/api/result.py
git commit -m "feat: support cookie OR API key authentication on all endpoints"
```

---

### Task 13: Dockerfile + Railway Config

**Files:**
- Create: `Dockerfile`, `railway.toml`

- [ ] **Step 1: Create Dockerfile**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Create railway.toml**

```toml
[build]
builder = "DOCKERFILE"
dockerfilePath = "Dockerfile"

[deploy]
startCommand = "uvicorn app.main:app --host 0.0.0.0 --port $PORT"
healthcheckPath = "/health"
healthcheckTimeout = 10
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 3
```

- [ ] **Step 3: Update main.py to use PORT from config**

At the bottom of `app/main.py`, add:

```python
if __name__ == "__main__":
    import uvicorn
    from app.config import PORT
    uvicorn.run(app, host="0.0.0.0", port=PORT)
```

- [ ] **Step 4: Build Docker image locally to verify**

Run:
```bash
cd /Users/zeoooo/contract-stamper
docker build -t contract-stamper . 2>&1 | tail -5
```
Expected: Successfully built / tagged

- [ ] **Step 5: Commit**

```bash
git add Dockerfile railway.toml app/main.py
git commit -m "feat: add Dockerfile and Railway deployment config"
```

---

### Task 14: File Cleanup Scheduler

**Files:**
- Modify: `app/main.py`

- [ ] **Step 1: Add background cleanup task**

Add to `app/main.py`:

```python
import asyncio
import time
import glob
from contextlib import asynccontextmanager
from app.config import UPLOAD_DIR, FILE_TTL_SECONDS


async def cleanup_old_files():
    """Periodically remove files older than FILE_TTL_SECONDS."""
    while True:
        await asyncio.sleep(300)  # Check every 5 minutes
        now = time.time()
        for directory in ["uploads", "stamps", "results", "previews"]:
            dir_path = os.path.join(UPLOAD_DIR, directory)
            if not os.path.exists(dir_path):
                continue
            for filepath in glob.glob(os.path.join(dir_path, "*")):
                if now - os.path.getmtime(filepath) > FILE_TTL_SECONDS:
                    os.remove(filepath)


@asynccontextmanager
async def lifespan(app_instance):
    task = asyncio.create_task(cleanup_old_files())
    yield
    task.cancel()
```

Then update the FastAPI app creation:

```python
app = FastAPI(title="Contract Stamper", version="0.1.0", lifespan=lifespan)
```

- [ ] **Step 2: Commit**

```bash
git add app/main.py
git commit -m "feat: add background file cleanup scheduler"
```

---

### Task 15: Integration Test + Push

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: Write integration test**

```python
import os
import time
import fitz
from PIL import Image
from fastapi.testclient import TestClient
from app.main import app


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
    from PIL import ImageDraw
    img = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([10, 10, 190, 190], outline=(200, 0, 0, 230), width=6)
    path = str(tmp_path / "stamp.png")
    img.save(path)
    return path


def test_full_workflow(tmp_path, monkeypatch):
    monkeypatch.setenv("API_KEY", "test-key")
    monkeypatch.setenv("WEB_PASSWORD", "test-pass")
    monkeypatch.setattr("app.config.UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr("app.core.pdf_processor.UPLOAD_DIR", str(tmp_path))

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
```

- [ ] **Step 2: Run all tests**

Run: `cd /Users/zeoooo/contract-stamper && python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add full workflow integration test"
```

- [ ] **Step 4: Push to GitHub**

```bash
git push -u origin main
```

- [ ] **Step 5: Add .gitignore**

```
__pycache__/
*.pyc
.env
*.egg-info/
dist/
build/
.pytest_cache/
```

```bash
git add .gitignore
git commit -m "chore: add .gitignore"
git push
```
