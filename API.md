# Contract Stamper API Reference

Base URL: `https://stamp.zeooo.cc` (or your deployment URL)

## Authentication

All API endpoints (except `/health`) require authentication via Bearer token.

```
Authorization: Bearer <API_KEY>
```

The `API_KEY` is configured as an environment variable on the server.

---

## Workflow

A typical stamping workflow follows these steps:

```
1. Upload contract    POST /api/v1/upload
2. List stamps        GET  /api/v1/stamps/list
3. Upload stamp       POST /api/v1/upload/stamp  (or use preset stamp)
4. Detect position    POST /api/v1/detect
5. Execute stamping   POST /api/v1/stamp
6. Poll status        GET  /api/v1/result/{task_id}
7. Download result    GET  /api/v1/download/{task_id}
```

---

## Endpoints

### Health Check

```
GET /health
```

No authentication required.

**Response:**
```json
{ "status": "ok" }
```

---

### Upload Contract

Upload a PDF or Word (.docx/.doc) contract file. Word files are automatically converted to PDF (tracked changes are accepted).

```
POST /api/v1/upload
Content-Type: multipart/form-data
```

**Request:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | File | Yes | PDF, DOCX, or DOC file |

**Response:**
```json
{
  "file_id": "a1b2c3d4e5f6",
  "page_count": 5,
  "previews": [
    "/api/v1/preview/a1b2c3d4e5f6_0.png",
    "/api/v1/preview/a1b2c3d4e5f6_1.png"
  ],
  "converted_from": ".docx"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `file_id` | string | 12-char hex ID, used in subsequent requests |
| `page_count` | integer | Total number of pages in the PDF |
| `previews` | string[] | URLs for page preview images |
| `converted_from` | string\|null | Original extension if converted, null if PDF |

**Example:**
```bash
curl -X POST https://stamp.zeooo.cc/api/v1/upload \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "file=@contract.docx"
```

---

### Upload Stamp Image

Upload a stamp/seal PNG image for use in the current stamping session.

```
POST /api/v1/upload/stamp
Content-Type: multipart/form-data
```

**Request:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | File | Yes | PNG image of the stamp/seal |

**Response:**
```json
{
  "stamp_id": "f6e5d4c3b2a1"
}
```

**Example:**
```bash
curl -X POST https://stamp.zeooo.cc/api/v1/upload/stamp \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "file=@company_seal.png"
```

---

### List Preset Stamps

Get all preset stamps configured by the admin.

```
GET /api/v1/stamps/list
```

**Response:**
```json
{
  "stamps": [
    {
      "name": "十字路口科技",
      "company": "十字路口科技",
      "filename": "crossing_seal.png",
      "url": "/stamps/files/crossing_seal.png"
    }
  ]
}
```

To use a preset stamp, download it from `url` and re-upload via `/api/v1/upload/stamp`, or fetch its content and upload programmatically.

---

### Detect Stamp Position

Automatically detect where to place the stamp by searching for keywords like "甲方（盖章）" or "乙方（盖章）" in the PDF.

```
POST /api/v1/detect
Content-Type: application/json
```

**Request:**
```json
{
  "file_id": "a1b2c3d4e5f6",
  "party": "乙方"
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `file_id` | string | Yes | - | File ID from upload |
| `party` | string | No | `"乙方"` | Which party's seal position to detect. Options: `"甲方"`, `"乙方"` |

**Response:**
```json
{
  "found": true,
  "positions": [
    {
      "page": 4,
      "x": 380.5,
      "y": 642.3,
      "keyword": "乙方（盖章）"
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `found` | boolean | Whether keywords were found |
| `positions` | array | List of detected positions |
| `positions[].page` | integer | 0-indexed page number |
| `positions[].x` | float | X coordinate in PDF points |
| `positions[].y` | float | Y coordinate in PDF points |
| `positions[].keyword` | string | The keyword that was matched |

**Example:**
```bash
curl -X POST https://stamp.zeooo.cc/api/v1/detect \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"file_id": "a1b2c3d4e5f6", "party": "乙方"}'
```

---

### Execute Stamping

Start the async stamping process. This places the seal, adds riding seam stamps, and optionally applies scan effects.

```
POST /api/v1/stamp
Content-Type: application/json
```

**Request:**
```json
{
  "file_id": "a1b2c3d4e5f6",
  "stamp_id": "f6e5d4c3b2a1",
  "party_b_position": {
    "page": 4,
    "x": 380.5,
    "y": 642.3
  },
  "riding_seam": true,
  "scan_effect": 50,
  "original_filename": "合同.docx"
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `file_id` | string | Yes | - | File ID from upload |
| `stamp_id` | string | Yes | - | Stamp ID from upload |
| `party_b_position` | object\|null | No | null | Seal placement position `{page, x, y}` |
| `party_b_position.page` | integer | Yes | - | 0-indexed page number |
| `party_b_position.x` | float | Yes | - | X coordinate in PDF points |
| `party_b_position.y` | float | Yes | - | Y coordinate in PDF points |
| `riding_seam` | boolean | No | true | Whether to add riding seam stamps across all pages |
| `scan_effect` | integer | No | 50 | Scan quality slider (0=no effect, 1-39=heavy, 40-79=medium, 80-100=light) |
| `original_filename` | string | No | "" | Original filename, used for the download filename |

**Response:**
```json
{
  "task_id": "b3c4d5e6f7a8"
}
```

**Example:**
```bash
curl -X POST https://stamp.zeooo.cc/api/v1/stamp \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "a1b2c3d4e5f6",
    "stamp_id": "f6e5d4c3b2a1",
    "party_b_position": {"page": 4, "x": 380.5, "y": 642.3},
    "riding_seam": true,
    "scan_effect": 50,
    "original_filename": "合同.docx"
  }'
```

---

### Poll Task Status

Check the progress of a stamping task.

```
GET /api/v1/result/{task_id}
```

**Response (processing):**
```json
{
  "task_id": "b3c4d5e6f7a8",
  "status": "processing",
  "progress": 60,
  "error": null
}
```

**Response (completed):**
```json
{
  "task_id": "b3c4d5e6f7a8",
  "status": "completed",
  "progress": 100,
  "error": null
}
```

**Response (error):**
```json
{
  "task_id": "b3c4d5e6f7a8",
  "status": "error",
  "progress": 30,
  "error": "Stamp file not found"
}
```

| Status | Description |
|--------|-------------|
| `pending` | Task created, not yet started |
| `processing` | Currently processing |
| `completed` | Done, ready to download |
| `error` | Failed, see `error` field |

**Recommended polling interval:** 800ms - 1s

---

### Download Result

Download the stamped PDF.

```
GET /api/v1/download/{task_id}
```

**Response:** Binary PDF file with `Content-Disposition` header using the original filename.

**Example:**
```bash
curl -o stamped_contract.pdf \
  https://stamp.zeooo.cc/api/v1/download/b3c4d5e6f7a8 \
  -H "Authorization: Bearer YOUR_API_KEY"
```

---

## Complete Workflow Example

```bash
API="https://stamp.zeooo.cc"
KEY="YOUR_API_KEY"
AUTH="Authorization: Bearer $KEY"

# 1. Upload contract
UPLOAD=$(curl -s -X POST "$API/api/v1/upload" \
  -H "$AUTH" -F "file=@contract.docx")
FILE_ID=$(echo $UPLOAD | jq -r '.file_id')
echo "File ID: $FILE_ID"

# 2. List available stamps
STAMPS=$(curl -s "$API/api/v1/stamps/list" -H "$AUTH")
STAMP_URL=$(echo $STAMPS | jq -r '.stamps[0].url')

# 3. Download preset stamp and re-upload
curl -s "$API$STAMP_URL" -H "$AUTH" -o /tmp/stamp.png
STAMP_UPLOAD=$(curl -s -X POST "$API/api/v1/upload/stamp" \
  -H "$AUTH" -F "file=@/tmp/stamp.png")
STAMP_ID=$(echo $STAMP_UPLOAD | jq -r '.stamp_id')
echo "Stamp ID: $STAMP_ID"

# 4. Detect seal position
DETECT=$(curl -s -X POST "$API/api/v1/detect" \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d "{\"file_id\": \"$FILE_ID\", \"party\": \"乙方\"}")
echo "Detection: $DETECT"

PAGE=$(echo $DETECT | jq '.positions[0].page')
X=$(echo $DETECT | jq '.positions[0].x')
Y=$(echo $DETECT | jq '.positions[0].y')

# 5. Execute stamping
STAMP_RESULT=$(curl -s -X POST "$API/api/v1/stamp" \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d "{
    \"file_id\": \"$FILE_ID\",
    \"stamp_id\": \"$STAMP_ID\",
    \"party_b_position\": {\"page\": $PAGE, \"x\": $X, \"y\": $Y},
    \"riding_seam\": true,
    \"scan_effect\": 50,
    \"original_filename\": \"contract.docx\"
  }")
TASK_ID=$(echo $STAMP_RESULT | jq -r '.task_id')
echo "Task ID: $TASK_ID"

# 6. Poll until completed
while true; do
  STATUS=$(curl -s "$API/api/v1/result/$TASK_ID" -H "$AUTH")
  S=$(echo $STATUS | jq -r '.status')
  echo "Status: $S ($(echo $STATUS | jq '.progress')%)"
  [ "$S" = "completed" ] && break
  [ "$S" = "error" ] && { echo "Error: $(echo $STATUS | jq -r '.error')"; exit 1; }
  sleep 1
done

# 7. Download result
curl -o stamped_contract.pdf "$API/api/v1/download/$TASK_ID" -H "$AUTH"
echo "Downloaded: stamped_contract.pdf"
```

---

## Scan Effect Quality Guide

The `scan_effect` parameter controls simulated scan quality (0-100):

| Range | Label | Description |
|-------|-------|-------------|
| 0 | Off | No scan effect applied |
| 80-100 | Light | High quality: minimal noise, slight tilt (0-0.8°) |
| 40-79 | Medium | Decent scan: visible noise, moderate tilt (0.8-1.5°), corner shadows |
| 1-39 | Heavy | Low quality: heavy noise, strong tilt (1.5-2.5°), dark corners and edges |

Effects include: brightness shift, sensor noise, page tilt, text softening, edge shadows, four-corner darkening, and non-uniform brightness.

---

## Error Responses

All errors follow this format:

```json
{
  "detail": "Error message description"
}
```

| Status Code | Description |
|------------|-------------|
| 400 | Bad request (invalid file format, missing fields) |
| 401 | Authentication required or invalid API key |
| 403 | Admin access required |
| 404 | Resource not found |
| 500 | Internal server error |

---

## Rate Limits & Notes

- Uploaded files are automatically cleaned up after **1 hour**
- Completed task results are purged after **1 hour**
- Maximum file size is limited by server configuration
- Word documents with tracked changes are automatically accepted (final version)
- The stamping process runs asynchronously; poll `/result/{task_id}` for progress
