import asyncio
import os
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.auth import verify_auth, validate_id
from app.config import UPLOAD_DIR
from app.core.stamp_placer import detect_keywords

router = APIRouter(prefix="/api/v1")


class DetectRequest(BaseModel):
    file_id: str
    party: str = "乙方"


@router.post("/detect")
async def detect(
    req: DetectRequest,
    _: str = Depends(verify_auth),
):
    validate_id(req.file_id)
    pdf_path = os.path.join(UPLOAD_DIR, "uploads", f"{req.file_id}.pdf")
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="File not found")
    positions = await asyncio.to_thread(detect_keywords, pdf_path, req.party)
    return {"found": len(positions) > 0, "positions": positions}
