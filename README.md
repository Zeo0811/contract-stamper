# Contract Stamper

An automated contract stamping tool that uploads Word/PDF contracts, auto-detects seal placement positions, applies digital seals with riding seam stamps, and simulates realistic scanning effects — outputting production-ready PDFs.

## Features

- **Multi-Format Upload** — Supports `.docx`, `.doc`, and `.pdf`. Word files are automatically converted to PDF (tracked changes are accepted, producing the final version).
- **Auto Seal Detection** — Searches for keywords like "Party A (Seal)" / "Party B (Seal)" in the document to automatically locate stamp positions. Manual click-to-place is also supported when keywords are not found.
- **Party Switching** — Toggle between Party A and Party B seal positions with one click.
- **Riding Seam Stamps** — Automatically slices the seal image across all pages and places each strip along the right edge, with random offset and rotation for a realistic hand-stamped look.
- **Scan Effect Simulation** — Adjustable intensity (light / medium / heavy) with a 7-layer processing pipeline: brightness shift, sensor noise, page tilt, text softening, non-uniform brightness, edge shadows, and four-corner darkening.
- **Admin Dashboard** — User management (create/delete users, role control) and stamp management (upload seal PNGs with associated company names).
- **Processing History** — View past stamping operations in-app with re-download support.
- **Completion Animation** — Fireworks celebration on successful processing.
- **RESTful API** — Full programmatic access to all features; supports MCP/Skill integration.
- **Multi-User Auth** — Session token + Bearer API key authentication with role-based access control.

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| **Backend** | Python 3.11, FastAPI, PyMuPDF (fitz), Pillow, NumPy |
| **Frontend** | Vanilla HTML/CSS/JS, PDF.js |
| **Document Conversion** | LibreOffice (headless), python-docx |
| **Deployment** | Docker, Railway |

## Quick Start

### Local Development

```bash
# 1. Install Python 3.11 and LibreOffice
# macOS
brew install python@3.11
brew install --cask libreoffice

# Ubuntu/Debian
sudo apt install python3.11 python3.11-venv libreoffice

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
│   ├── main.py              # FastAPI entry point, route mounting, auth endpoints
│   ├── config.py             # Environment variable configuration
│   ├── auth.py               # Multi-user auth system (token + API key)
│   ├── api/
│   │   ├── upload.py         # File upload (PDF/Word), Word→PDF conversion
│   │   ├── detect.py         # Keyword-based seal position detection
│   │   ├── stamp.py          # Async stamping (seal + riding seam + scan effect)
│   │   ├── result.py         # Task status polling and result download
│   │   └── admin.py          # Admin API (user/stamp management)
│   ├── core/
│   │   ├── pdf_processor.py  # PDF reading and preview rendering
│   │   ├── stamp_placer.py   # Keyword detection + seal overlay
│   │   ├── seam_stamp.py     # Riding seam stamp slicing and placement
│   │   └── scan_effect.py    # Scan effect simulation (7-layer pipeline)
│   ├── static/
│   │   ├── css/style.css     # Green theme styling
│   │   ├── js/
│   │   │   ├── app.js        # Main page interaction logic
│   │   │   └── admin.js      # Admin dashboard logic
│   │   ├── stamps/           # Preset stamp directory (admin-managed)
│   │   ├── icons/            # PWA icons (16–512px)
│   │   ├── logo.png          # Brand logo
│   │   ├── favicon.ico
│   │   └── manifest.json     # PWA manifest
│   └── templates/
│       ├── index.html        # Main user interface
│       └── admin.html        # Admin dashboard
├── tests/
│   ├── conftest.py           # Test fixtures (sample PDF, stamp)
│   ├── test_detect.py        # Keyword detection tests
│   ├── test_stamp_placer.py  # Stamp placement tests
│   ├── test_seam_stamp.py    # Riding seam tests
│   ├── test_scan_effect.py   # Scan effect tests
│   └── test_integration.py   # End-to-end workflow tests
├── Dockerfile                # Docker build configuration
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
| `POST` | `/upload` | Upload a contract file (PDF/Word), returns `file_id` |
| `POST` | `/upload/stamp` | Upload a seal PNG image, returns `stamp_id` |
| `GET` | `/stamps/list` | List all preset stamps with metadata |
| `POST` | `/detect` | Auto-detect seal positions by keyword (Party A/B) |
| `POST` | `/stamp` | Start async stamping process, returns `task_id` |
| `GET` | `/result/{task_id}` | Poll task status and progress (0–100%) |
| `GET` | `/download/{task_id}` | Download the stamped PDF result |
| `POST` | `/login` | User authentication, returns session token |
| `GET` | `/me` | Get current user info |
| `GET` | `/health` | Health check (no auth required) |

### Typical Workflow

```
Upload contract → Upload/select stamp → Detect position → Execute stamping → Poll status → Download result
```

### Quick Example (cURL)

```bash
API="https://your-deployment-url.com"
KEY="YOUR_API_KEY"
AUTH="Authorization: Bearer $KEY"

# 1. Upload contract
UPLOAD=$(curl -s -X POST "$API/api/v1/upload" -H "$AUTH" -F "file=@contract.docx")
FILE_ID=$(echo $UPLOAD | jq -r '.file_id')

# 2. Upload seal image
STAMP_UPLOAD=$(curl -s -X POST "$API/api/v1/upload/stamp" -H "$AUTH" -F "file=@seal.png")
STAMP_ID=$(echo $STAMP_UPLOAD | jq -r '.stamp_id')

# 3. Auto-detect seal position
DETECT=$(curl -s -X POST "$API/api/v1/detect" \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d "{\"file_id\": \"$FILE_ID\", \"party\": \"乙方\"}")

PAGE=$(echo $DETECT | jq '.positions[0].page')
X=$(echo $DETECT | jq '.positions[0].x')
Y=$(echo $DETECT | jq '.positions[0].y')

# 4. Execute stamping
TASK_ID=$(curl -s -X POST "$API/api/v1/stamp" \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d "{
    \"file_id\": \"$FILE_ID\",
    \"stamp_id\": \"$STAMP_ID\",
    \"party_b_position\": {\"page\": $PAGE, \"x\": $X, \"y\": $Y},
    \"riding_seam\": true,
    \"scan_effect\": 50,
    \"original_filename\": \"contract.docx\"
  }" | jq -r '.task_id')

# 5. Poll until completed
while true; do
  STATUS=$(curl -s "$API/api/v1/result/$TASK_ID" -H "$AUTH")
  S=$(echo $STATUS | jq -r '.status')
  echo "Status: $S ($(echo $STATUS | jq '.progress')%)"
  [ "$S" = "completed" ] && break
  [ "$S" = "error" ] && { echo "Error: $(echo $STATUS | jq -r '.error')"; exit 1; }
  sleep 1
done

# 6. Download result
curl -o stamped_contract.pdf "$API/api/v1/download/$TASK_ID" -H "$AUTH"
echo "Downloaded: stamped_contract.pdf"
```

## Scan Effect Quality

The `scan_effect` parameter (0–100) controls simulated scan quality:

| Range | Label | Description |
|-------|-------|-------------|
| **0** | Off | No scan effect applied |
| **80–100** | Light | High quality: minimal noise, slight tilt (0–0.8°), DPI 200 |
| **40–79** | Medium | Balanced: visible noise, moderate tilt (0.8–1.5°), DPI 150–200 |
| **1–39** | Heavy | Low quality: heavy noise, strong tilt (1.5–2.5°), dark corners, DPI 120–150 |

The 7-layer scan effect pipeline includes:

1. **Brightness shift** — Simulates scanner light source
2. **Non-uniform brightness** — Sensor characteristics with horizontal banding
3. **Text softening** — Optical capture simulation
4. **Luminance-weighted noise** — Sensor noise modeling
5. **Random tilt** — Page misalignment effect
6. **Edge shadow** — Page lift effect along edges
7. **Four-corner darkening** — Vignetting effect

## Testing

```bash
# Run all tests
pytest tests/

# Run with verbose output
pytest tests/ -v

# Run a specific test file
pytest tests/test_detect.py -v

# Run with coverage
pytest tests/ --cov=app
```

## Authentication

The application supports two authentication methods:

1. **Session Token** — Obtained via the `/login` endpoint. Tokens are stored in-memory with a 24-hour TTL. Used by the web interface.
2. **API Key** — Configured via the `API_KEY` environment variable. Passed as a Bearer token in the `Authorization` header. Used for programmatic API access.

### User Roles

| Role | Permissions |
|------|------------|
| `admin` | Full access: stamp contracts, manage users, manage stamps |
| `user` | Standard access: stamp contracts, view history |

Admin users can manage other users and stamps through the admin dashboard at `/admin`.

## Storage

The application uses file-based storage (no database required):

- **Temporary storage** (`UPLOAD_DIR`): Uploaded files, stamps, previews, and results. Auto-cleaned after `FILE_TTL_SECONDS` (default: 1 hour).
- **Persistent storage** (`DATA_DIR`): User accounts (`users.json`), stamp metadata (`stamps_meta.json`), and preset stamp images.

## License

MIT
