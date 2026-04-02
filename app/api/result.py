import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from app.auth import verify_auth, validate_id
from app.api.stamp import tasks

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
