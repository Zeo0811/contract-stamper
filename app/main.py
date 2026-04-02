import os
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from app.config import UPLOAD_DIR, WEB_PASSWORD
from app.auth import verify_web_password, set_web_session

from app.api.upload import router as upload_router
from app.api.detect import router as detect_router
from app.api.stamp import router as stamp_router
from app.api.result import router as result_router

app = FastAPI(title="Contract Stamper", version="0.1.0")
app.include_router(upload_router)
app.include_router(detect_router)
app.include_router(stamp_router)
app.include_router(result_router)

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(os.path.join(UPLOAD_DIR, "uploads"), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_DIR, "stamps"), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_DIR, "results"), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_DIR, "previews"), exist_ok=True)

static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "authenticated": verify_web_password(request),
    })


@app.post("/login")
async def login(password: str = Form(...)):
    if password != WEB_PASSWORD:
        return RedirectResponse(url="/?error=1", status_code=303)
    response = RedirectResponse(url="/", status_code=303)
    set_web_session(response)
    return response


@app.get("/api/v1/preview/{filename}")
async def serve_preview(filename: str):
    path = os.path.join(UPLOAD_DIR, "previews", filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404)
    return FileResponse(path)


if __name__ == "__main__":
    import uvicorn
    from app.config import PORT
    uvicorn.run(app, host="0.0.0.0", port=PORT)
