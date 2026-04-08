# Contract Stamper

An automated contract stamping tool that uploads PDF/Word/Excel contracts, auto-detects seal placement positions via text search and OCR, applies digital seals with riding seam stamps, and simulates realistic scanning effects — outputting production-ready PDFs.

## Features

- **Multi-Format Upload** — Supports `.pdf`, `.docx`, `.doc`, `.xlsx`, `.xls`. Word and Excel files are automatically converted to PDF via LibreOffice.
- **Auto Seal Detection** — Three-tier detection: PyMuPDF text search → Unicode-normalized fallback → Tesseract OCR for scanned documents. Scans from the last page backward to prioritize signature blocks.
- **Party Switching** — Toggle between Party A (甲方) and Party B (乙方) seal positions with one click. Switching automatically re-detects the position.
- **Riding Seam Stamps** — Slices the seal across all pages along the right edge, with configurable vertical position (random / top / center / bottom) and per-page jitter for a natural look.
- **Stamp Aging Effect** — Adjustable intensity (0–100) simulating real stamp impressions: ink fade via transparency, mild desaturation, uneven pressure map, Gaussian blur, noise, and random rotation (±3° to ±10°). Red color is preserved even at high intensity.
- **Scan Effect Simulation** — Adjustable intensity with a 7-layer pipeline: brightness shift, sensor noise, page tilt, text softening, non-uniform brightness, edge shadows, and four-corner darkening.
- **Instant Stamp Selection** — All stamps are pre-uploaded in the background when the page loads. Clicking a stamp is instant with no loading delay.
- **Normalized Coordinates** — Seal positions use 0–1 normalized coordinates, ensuring correct marker placement regardless of browser window size.
- **Excel Support** — Excel files are converted to PDF, with seam stamps auto-disabled and manual stamp placement via click.
- **Admin Dashboard** — User management (create/delete, role control) and stamp management (upload seal PNGs with company names, image preview, upload progress indicator).
- **Cache-Busting** — Static files include a deploy timestamp query parameter, ensuring browsers load fresh JS/CSS after every deployment.
- **Processing History** — View past stamping operations with re-download support.
- **Completion Animation** — Fireworks celebration on successful processing.
- **RESTful API** — Full programmatic access; supports MCP/Skill integration.
- **Multi-User Auth** — Session token + Bearer API key with role-based access control.

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| **Backend** | Python 3.11, FastAPI, PyMuPDF (fitz), Pillow, NumPy, pytesseract |
| **Frontend** | Vanilla HTML/CSS/JS, PDF.js |
| **OCR** | Tesseract (chi_sim + chi_tra + eng) |
| **Document Conversion** | LibreOffice (headless) — Writer + Calc |
| **Deployment** | Docker, Railway |

## Quick Start

### Local Development

```bash
# 1. Install Python 3.11, LibreOffice, and Tesseract
# macOS
brew install python@3.11 tesseract tesseract-lang
brew install --cask libreoffice

# Ubuntu/Debian
sudo apt install python3.11 python3.11-venv libreoffice tesseract-ocr \
  tesseract-ocr-chi-sim tesseract-ocr-chi-tra

# 2. Create virtual environment and install dependencies
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Start the server
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 4. Open in browser
# http://localhost:8000
# Default admin credentials: admin / admin123
```

### Docker

```bash
docker build -t contract-stamper .
docker run -p 8000:8000 \
  -e ADMIN_PASSWORD=your_admin_password \
  -e API_KEY=your_api_key \
  contract-stamper
```

### Railway Deployment

1. Fork this repository
2. Create a new Railway project and connect the GitHub repo
3. Set environment variables:
   - `ADMIN_PASSWORD` — Admin account password
   - `API_KEY` — API access key
   - `PORT` — Port number (auto-set by Railway)

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ADMIN_PASSWORD` | `admin123` | Admin account password |
| `API_KEY` | `dev-key` | Bearer token for API authentication |
| `WEB_PASSWORD` | `dev-pass` | Web interface password |
| `PORT` | `8000` | HTTP server port |
| `UPLOAD_DIR` | `/tmp/contract-stamper` | Temporary file storage directory |
| `DATA_DIR` | `./data` | Persistent data storage (users, stamp metadata) |
| `FILE_TTL_SECONDS` | `3600` | Auto-cleanup interval for uploaded/result files (seconds) |

## Project Structure

```
contract-stamper/
├── app/
│   ├── main.py              # FastAPI entry point, route mounting, auth, cache-busting
│   ├── config.py             # Environment variable configuration
│   ├── auth.py               # Multi-user auth system (token + API key)
│   ├── api/
│   │   ├── upload.py         # File upload (PDF/Word/Excel), conversion to PDF
│   │   ├── detect.py         # 3-tier seal position detection (text + normalize + OCR)
│   │   ├── stamp.py          # Async stamping (seal + aging + riding seam + scan effect)
│   │   ├── result.py         # Task status polling and result download
│   │   └── admin.py          # Admin API (user/stamp management, UUID filenames)
│   ├── core/
│   │   ├── pdf_processor.py  # PDF reading and preview rendering
│   │   ├── stamp_placer.py   # Keyword detection, OCR, seal aging + overlay
│   │   ├── seam_stamp.py     # Riding seam stamp slicing and placement
│   │   └── scan_effect.py    # Scan effect simulation (7-layer pipeline)
│   ├── static/
│   │   ├── css/style.css     # Design system (green theme, focus states, responsive)
│   │   ├── js/
│   │   │   ├── app.js        # Main page (normalized coords, preload, resize handler)
│   │   │   └── admin.js      # Admin dashboard (upload progress, image preview)
│   │   ├── stamps/           # Preset stamp directory (admin-managed)
│   │   ├── icons/            # PWA icons (16–512px)
│   │   ├── logo.png          # Brand logo
│   │   ├── favicon.ico
│   │   └── manifest.json     # PWA manifest
│   └── templates/
│       ├── index.html        # Main UI (cache-busted static refs)
│       └── admin.html        # Admin dashboard
├── tests/
├── Dockerfile                # Python 3.11 + LibreOffice Writer/Calc + Tesseract OCR
├── railway.toml              # Railway deployment configuration
├── requirements.txt          # Python dependencies
├── API.md                    # Full API reference
└── .env.example              # Environment variable template
```

## API Overview

Full API documentation is available in **[API.md](API.md)**.

**Base URL:** `/api/v1` — Requires `Authorization: Bearer <API_KEY>` header.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/upload` | Upload a contract file (PDF/Word/Excel), returns `file_id` |
| `POST` | `/upload/stamp` | Upload a seal PNG image, returns `stamp_id` |
| `GET` | `/stamps/list` | List all preset stamps with metadata |
| `POST` | `/detect` | Auto-detect seal positions (text search + OCR fallback) |
| `POST` | `/stamp` | Start async stamping, returns `task_id` |
| `GET` | `/result/{task_id}` | Poll task status and progress (0–100%) |
| `GET` | `/download/{task_id}` | Download the stamped PDF result |
| `POST` | `/login` | User authentication, returns session token |
| `GET` | `/me` | Get current user info |
| `GET` | `/health` | Health check (no auth required) |

### Typical Workflow

```
Upload contract → Upload/select stamp → Detect position → Execute stamping → Poll status → Download result
```

## Stamp Aging Effect

The `stamp_aging` parameter (0–100, default 70) controls how realistic the seal impression looks:

| Range | Label | Description |
|-------|-------|-------------|
| **0** | Off | No aging effect, original stamp image |
| **1–25** | Light | Subtle fade, slight blur and rotation (±5°) |
| **26–55** | Medium | Noticeable fade, uneven ink, blur, noise |
| **56–100** | Heavy | Strong transparency fade, large rotation (±10°), heavy pressure variation |

The aging effect preserves the stamp's red color — fading is achieved primarily through alpha transparency rather than desaturation.

## Scan Effect Quality

The `scan_effect` parameter (0–100) controls simulated scan quality:

| Range | Label | Description |
|-------|-------|-------------|
| **0** | Off | No scan effect applied |
| **80–100** | Light | High quality: minimal noise, slight tilt, DPI 200 |
| **40–79** | Medium | Balanced: visible noise, moderate tilt, DPI 150–200 |
| **1–39** | Heavy | Low quality: heavy noise, strong tilt, dark corners, DPI 120–150 |

## Changelog

### v1.1.0 (2026-04-08)

**Seal Upload & Display**
- Fixed thumbnail display for PNG stamps (UUID-based filenames bypass regex validation)
- Added upload progress spinner and image preview in admin panel
- Cache-busting (`?v=timestamp`) for static files — no more stale JS/CSS after deploy

**Seal Position Detection**
- Three-tier detection: PyMuPDF text → Unicode normalization → Tesseract OCR (scanned PDFs)
- Scans from last page backward (signature blocks are at the end)
- Expanded keyword list: 34 variations including plain "甲方：" / "乙方：" format
- Normalized 0–1 coordinate system eliminates browser-width-dependent marker drift
- Marker repositions correctly on window resize

**Stamp Aging Effect**
- Configurable intensity (0–100) via UI slider, default 70
- Red color preserved even at heavy intensity (fading via alpha, not desaturation)
- Wider rotation range: ±3° base up to ±10° at full intensity
- Uneven ink pressure, Gaussian blur, noise all scale with intensity

**Riding Seam Stamps**
- Configurable vertical position: random / top / center / bottom
- Default position: top (~20% page height)
- Wider randomization range with per-page jitter

**Excel Support**
- Upload `.xlsx` / `.xls` files (converted to PDF via LibreOffice Calc)
- Auto-disables seam stamps, prompts manual stamp placement

**UI/UX Improvements**
- Instant stamp selection via background preloading
- Word document preview waits for all images before detection
- Circular reset button with rotate-on-hover animation
- Focus-visible keyboard accessibility for all interactive elements
- Consistent design tokens (colors, borders, shadows)
- Seam position dropdown styled to match design system
- Preloaded stamps show green dot indicator

**Bug Fixes**
- Manual click position now correctly overrides auto-detection
- Fixed coordinate system mismatch between PDF points and canvas pixels
- Fixed Word upload marker not scrolling to detected page

### v1.0.0

Initial release with PDF/Word upload, keyword detection, riding seam stamps, scan effect simulation, admin dashboard, and multi-user auth.

## Testing

```bash
pytest tests/ -v
pytest tests/ --cov=app
```

## Authentication

Two authentication methods:

1. **Session Token** — Via `/login` endpoint, 24-hour TTL, used by web interface.
2. **API Key** — Via `API_KEY` env var, passed as Bearer token, used for programmatic access.

| Role | Permissions |
|------|------------|
| `admin` | Full access: stamp contracts, manage users, manage stamps |
| `user` | Standard access: stamp contracts, view history |

## License

MIT
