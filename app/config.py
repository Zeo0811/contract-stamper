import os

API_KEY = os.environ.get("API_KEY", "dev-key")
WEB_PASSWORD = os.environ.get("WEB_PASSWORD", "dev-pass")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
PORT = int(os.environ.get("PORT", "8000"))
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "/tmp/contract-stamper")
DATA_DIR = os.environ.get("DATA_DIR", "./data")  # Persistent storage (Railway Volume)
FILE_TTL_SECONDS = 3600  # 1 hour
