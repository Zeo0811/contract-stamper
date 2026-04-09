import os
import base64
import logging
from datetime import date
import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from app.auth import verify_auth, validate_id
from app.api.stamp import tasks
from app.config import RESEND_API_KEY, MAIL_FROM, MAIL_TO

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")


@router.get("/result/{task_id}")
async def get_result(
    task_id: str,
    _: str = Depends(verify_auth),
):
    validate_id(task_id)
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
    _: str = Depends(verify_auth),
):
    validate_id(task_id)
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    task = tasks[task_id]
    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail="Task not completed")
    result_path = task["result_path"]
    if not os.path.exists(result_path):
        raise HTTPException(status_code=404, detail="Result file not found")
    original = task.get("original_filename", "")
    if original:
        base = os.path.splitext(original)[0]
        download_name = f"{base}.pdf"
    else:
        download_name = f"stamped_{task_id}.pdf"

    return FileResponse(
        result_path,
        media_type="application/pdf",
        filename=download_name,
    )


def _build_subject(party_a: str, party_b: str) -> str:
    """Build email subject: 【合同+日期+甲方乙方主体名称】"""
    today = date.today().strftime("%Y%m%d")
    parts = ["合同", today]
    names = []
    if party_a:
        names.append(party_a)
    if party_b:
        names.append(party_b)
    if names:
        parts.append("&".join(names))
    return "【" + " ".join(parts) + "】"


class SendEmailRequest(BaseModel):
    task_id: str


@router.post("/send-email")
async def send_email(
    req: SendEmailRequest,
    _: str = Depends(verify_auth),
):
    if not RESEND_API_KEY or not MAIL_TO:
        raise HTTPException(status_code=500, detail="邮件未配置，请设置 RESEND_API_KEY 和 MAIL_TO")

    validate_id(req.task_id)
    if req.task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    task = tasks[req.task_id]
    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail="Task not completed")
    result_path = task["result_path"]
    if not os.path.exists(result_path):
        raise HTTPException(status_code=404, detail="Result file not found")

    original = task.get("original_filename", "")
    filename = f"{os.path.splitext(original)[0]}.pdf" if original else f"stamped_{req.task_id}.pdf"
    subject = _build_subject(task.get("party_a", ""), task.get("party_b", ""))

    # Read PDF and base64 encode for Resend attachment
    with open(result_path, "rb") as f:
        pdf_b64 = base64.b64encode(f.read()).decode()

    payload = {
        "from": MAIL_FROM,
        "to": [MAIL_TO],
        "subject": subject,
        "text": f"{filename} 已完成盖章，请查收附件。",
        "attachments": [
            {
                "filename": filename,
                "content": pdf_b64,
            }
        ],
    }

    logger.info(f"Sending email via Resend: to={MAIL_TO}, subject={subject}")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
                json=payload,
            )
        if resp.status_code >= 400:
            detail = resp.json().get("message", resp.text)
            logger.error(f"Resend API error: {resp.status_code} {detail}")
            raise HTTPException(status_code=500, detail=f"发送失败: {detail}")
    except httpx.HTTPError as e:
        logger.error(f"Resend request failed: {e}")
        raise HTTPException(status_code=500, detail=f"发送失败: {str(e)}")

    logger.info("Email sent successfully via Resend")
    return {"ok": True, "to": MAIL_TO}
