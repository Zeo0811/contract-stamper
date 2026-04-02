# Contract Stamper - Design Spec

## Overview

A web-based tool for automatically stamping contracts with company seals and generating scan-like PDF output. Supports automatic keyword-based seal positioning, riding seam stamps (骑缝章), and configurable simulated scan effects.

Deployed on Railway as a public web service with API endpoints for skill/MCP integration.

## Tech Stack

- **Backend**: Python 3.11 + FastAPI + PyMuPDF (fitz) + Pillow
- **Frontend**: Vanilla HTML/CSS/JS + PDF.js
- **Deployment**: Docker on Railway

## Module 1: PDF Processing Engine

### Seal Positioning (Auto + Manual)

**Auto detection:**
- Use PyMuPDF `page.search_for()` to search for keywords: "乙方（盖章）", "乙方签章", "乙方（签字/盖章）", "乙方（签字盖章）"
- Returns coordinate rectangles of matched text
- Seal center aligns slightly below/right of the keyword region

**Manual fallback:**
- When no keywords are found, API returns page preview images and prompts user to click
- Frontend captures click coordinates on rendered PDF, converts to PDF coordinate space (accounting for scale ratio)

### Riding Seam Stamp (骑缝章)

- Input: full stamp PNG + total page count N
- Slice stamp image into N vertical strips (equal width)
- Each strip gets random micro-offset: horizontal ±2px, vertical ±3px, rotation ±0.5°
- Each strip placed at the right edge of its corresponding page, vertically centered
- Strip right edge aligns with page right edge

### Seal Overlay

- PNG stamp with alpha channel converted to PDF-compatible format
- Inserted via PyMuPDF `page.insert_image()` at target coordinates
- Default size: ~42mm diameter (standard Chinese company seal), configurable

## Module 2: Simulated Scan Effect

### Pipeline

PDF pages → render to high-res images → apply scan effects → reassemble into PDF

Scan effects are applied AFTER stamping so seals also carry scan texture.

### Configurable Parameters (Scan Quality Slider 0-100)

| Parameter | Light (80-100) | Medium (40-80) | Heavy (0-40) |
|-----------|----------------|-----------------|---------------|
| Paper tint | Slight warm yellow | Noticeable warm yellow | Grayish, aged |
| Noise | Minimal | Light grain | Visible grain |
| Page tilt | 0-0.3° | 0.3-0.8° | 0.8-1.5° |
| Blur | None | Light Gaussian | Noticeable blur |
| Edge shadow | None | Light vignette | Visible scanner edge shadow |
| Render DPI | 300 | 200 | 150 |

### Implementation

- Render each page: `page.get_pixmap(dpi=target_dpi)`
- Apply with Pillow in order: paper tint overlay → noise → rotation → Gaussian blur → vignette
- Reassemble processed images into new PDF via PyMuPDF

## Module 3: Web Frontend

### Design Style

Inherits the organic green aesthetic from the end_to_end-layout project:

**Colors:**
- Primary: `#407600` (organic green) with gradient variants
- Dark hover: `#356200`
- Light accent: `#f4f9ed`
- Border accent: `#c5e0a5`
- Text: `#1a1a1a` (primary), `#666` (secondary)
- Background: `#f0f2f5` (page), `#fff` (cards)

**Design tokens:**
- Border radius: 8px (buttons), 12px (cards), 16px (modals)
- Shadows: `0 1px 4px rgba(0,0,0,.06)` (cards), `0 8px 32px` (modals)
- Transitions: `.2s ease` for hover/focus states
- Focus: green border + `0 0 0 3px rgba(64,118,0,.1)` glow

**Typography:**
- System font stack: `-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'PingFang SC', sans-serif`
- Monospace for logs: `'SF Mono', Monaco, Consolas`

**Interactions:**
- Frosted glass modals: `backdrop-filter: blur(4px)`, scale animation 0.9→1.0
- Primary buttons: linear green gradient with shadow
- Progress fill animation on "Process" button during execution

### Layout

Single page, left-right split:

**Left panel (~320px) - Controls:**
- Upload area (drag & drop + click) for PDF and stamp PNG
- Seal size slider
- Riding seam stamp toggle
- Scan effect quality slider (0-100) with single-page preview button
- Green gradient "Start Processing" button with progress fill animation

**Right panel - PDF Preview:**
- PDF.js renderer in white card container
- Auto-detect success: green dashed border highlighting detected seal position, draggable to adjust
- Auto-detect failure: click to specify position
- Post-processing: switches to result PDF preview + download button

**Mobile responsive:**
- Stacks vertically, control panel becomes bottom drawer

**Authentication:**
- Password wall on first visit, frosted glass overlay
- Mobile: bottom sheet login (`border-radius: 20px 20px 0 0`)
- Session cookie valid 24 hours
- Password configured via `WEB_PASSWORD` env var

## Module 4: API Design

**Base URL:** `/api/v1`

**Authentication:** `Authorization: Bearer <API_KEY>` header on all requests. Key set via `API_KEY` env var.

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/upload` | Upload PDF contract, returns file_id + page preview URLs |
| POST | `/upload/stamp` | Upload stamp PNG, returns stamp_id |
| POST | `/detect` | Auto-detect seal positions by keyword search |
| POST | `/stamp` | Execute stamping + scan effect (async) |
| GET | `/result/{task_id}` | Poll processing status |
| GET | `/download/{task_id}` | Download processed PDF |

### Request/Response Examples

**POST `/stamp`:**
```json
{
  "file_id": "abc123",
  "stamp_id": "stamp456",
  "party_b_position": {"page": 5, "x": 400, "y": 650},
  "riding_seam": true,
  "scan_effect": 65
}
```

**POST `/detect` response:**
```json
{
  "found": true,
  "positions": [
    {
      "keyword": "乙方（盖章）",
      "page": 5,
      "x": 380,
      "y": 620,
      "width": 120,
      "height": 30
    }
  ]
}
```

**Async processing:** `/stamp` returns `{"task_id": "..."}`, frontend polls `/result/{task_id}` for status updates.

### Skill/MCP Integration

The API is designed for direct consumption by MCP servers or Claude Code skills. An agent workflow:
1. `POST /upload` → get file_id
2. `POST /upload/stamp` → get stamp_id
3. `POST /detect` → get positions (or specify manually)
4. `POST /stamp` → get task_id
5. `GET /result/{task_id}` → poll until complete
6. `GET /download/{task_id}` → download result

## Module 5: Project Structure

```
contract-stamper/
├── app/
│   ├── main.py              # FastAPI entry, mount routes and static files
│   ├── config.py             # Env var configuration
│   ├── auth.py               # API Key + Web password session
│   ├── api/
│   │   ├── upload.py         # Upload endpoints
│   │   ├── detect.py         # Keyword detection endpoint
│   │   ├── stamp.py          # Stamping + scan effect endpoint
│   │   └── result.py         # Result query + download
│   ├── core/
│   │   ├── pdf_processor.py  # PDF read, render, reassemble
│   │   ├── stamp_placer.py   # Seal positioning and overlay
│   │   ├── seam_stamp.py     # Riding seam stamp slicing and placement
│   │   └── scan_effect.py    # Simulated scan effect processing
│   ├── static/
│   │   ├── css/style.css
│   │   └── js/app.js
│   └── templates/
│       └── index.html
├── tests/
│   ├── test_detect.py
│   ├── test_stamp.py
│   ├── test_seam.py
│   └── test_scan_effect.py
├── Dockerfile
├── requirements.txt
├── railway.toml
└── .env.example
```

### Dependencies

```
fastapi
uvicorn
PyMuPDF
Pillow
python-multipart
```

### Railway Deployment

- `railway.toml`: build and start commands
- Environment variables: `API_KEY`, `WEB_PASSWORD`, `PORT`
- File storage: `/tmp` directory, auto-cleanup after 1 hour
- Docker base: `python:3.11-slim`

## MVP Scope

Single stamp support (one company seal PNG for both party-B stamp and riding seam stamp). Architecture allows future extension to multiple stamps with different roles.

## Out of Scope (Future)

- Multiple stamp types (legal representative seal, finance seal)
- Batch processing multiple contracts
- OCR-based contract content extraction
- Digital signature / CA certification
