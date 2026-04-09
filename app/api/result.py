import os
import smtplib
import asyncio
import logging
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.text import MIMEText
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from app.auth import verify_auth, validate_id
from app.api.stamp import tasks
from app.config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, MAIL_TO

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


def _send_email(to: str, pdf_path: str, filename: str, subject: str):
    """Send stamped PDF as email attachment via Gmail SMTP."""
    # Gmail app passwords work both with and without spaces
    password = SMTP_PASSWORD.strip()

    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = to
    msg.attach(MIMEText(f"{filename} 已完成盖章，请查收附件。", "plain", "utf-8"))

    with open(pdf_path, "rb") as f:
        att = MIMEApplication(f.read(), Name=filename)
        att["Content-Disposition"] = f'attachment; filename="{filename}"'
        msg.attach(att)

    logger.info(f"Sending email: from={SMTP_USER} to={to} host={SMTP_HOST}:{SMTP_PORT}")

    # Try SSL first (port 465), then STARTTLS (port 587) as fallback
    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=15) as s:
            s.login(SMTP_USER, password)
            s.send_message(msg)
    except Exception as ssl_err:
        logger.warning(f"SMTP_SSL failed: {ssl_err}, trying STARTTLS on 587")
        with smtplib.SMTP(SMTP_HOST, 587, timeout=15) as s:
            s.starttls()
            s.login(SMTP_USER, password)
            s.send_message(msg)

    logger.info("Email sent successfully")


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
    subject = _build_subject(task.get("party_a", ""), task.get("party_b", ""))

    try:
        await asyncio.to_thread(_send_email, MAIL_TO, result_path, filename, subject)
    except Exception as e:
        logger.error(f"Email send failed: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=f"发送失败: {str(e)}")

    return {"ok": True, "to": MAIL_TO}


@router.get("/email-check")
async def email_check(_: str = Depends(verify_auth)):
    """Diagnostic: check email configuration without sending."""
    configured = bool(SMTP_USER and SMTP_PASSWORD and MAIL_TO)
    result = {
        "configured": configured,
        "smtp_host": SMTP_HOST,
        "smtp_port": SMTP_PORT,
        "smtp_user": SMTP_USER[:3] + "***" if SMTP_USER else "",
        "mail_to": MAIL_TO[:3] + "***" if MAIL_TO else "",
        "password_set": bool(SMTP_PASSWORD),
        "password_len": len(SMTP_PASSWORD) if SMTP_PASSWORD else 0,
    }
    if configured:
        try:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=10) as s:
                s.login(SMTP_USER, SMTP_PASSWORD.strip())
                result["smtp_login"] = "ok"
        except Exception as e:
            result["smtp_login"] = f"failed: {type(e).__name__}: {e}"
    return result
