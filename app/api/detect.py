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
    return {"found": len(positions) > 0, "positions": positions}
