import os
import smtplib
import asyncio
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.text import MIMEText
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from app.auth import verify_auth, validate_id
from app.api.stamp import tasks
from app.config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, MAIL_TO

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
    # Use original filename if available
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


def _send_email(to: str, pdf_path: str, filename: str):
    """Send stamped PDF as email attachment via Gmail SMTP."""
    msg = MIMEMultipart()
    msg["Subject"] = f"盖章完成: {filename}"
    msg["From"] = SMTP_USER
    msg["To"] = to
    msg.attach(MIMEText(f"{filename} 已完成盖章，请查收附件。", "plain", "utf-8"))

    with open(pdf_path, "rb") as f:
        att = MIMEApplication(f.read(), Name=filename)
        att["Content-Disposition"] = f'attachment; filename="{filename}"'
        msg.attach(att)

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as s:
        s.login(SMTP_USER, SMTP_PASSWORD)
        s.send_message(msg)


class SendEmailRequest(BaseModel):
    task_id: str


@router.post("/send-email")
async def send_email(
    req: SendEmailRequest,
    _: str = Depends(verify_auth),
):
    if not SMTP_USER or not SMTP_PASSWORD or not MAIL_TO:
        raise HTTPException(status_code=500, detail="邮件未配置")

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

    try:
        await asyncio.to_thread(_send_email, MAIL_TO, result_path, filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"发送失败: {str(e)}")

    return {"ok": True, "to": MAIL_TO}
