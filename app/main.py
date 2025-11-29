import logging
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.api_v1.api import api_router

# --- CẤU HÌNH LOGGING TẬP TRUNG ---
# Tạo format log: [Thời gian] [Mức độ] [Tên Module] Nội dung
LOG_FORMAT = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"

# Cấu hình logging ra màn hình (Stdout) để Docker bắt được
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[
        logging.StreamHandler(sys.stdout)
    ],
    force=True
)

# Lấy logger gốc để đảm bảo các thư viện con cũng in ra được
logger = logging.getLogger(__name__)
# ----------------------------------

app = FastAPI(title=settings.PROJECT_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.on_event("startup")
async def startup_event():
    logger.info("🚀 AI Middleware đã khởi động thành công!")
    logger.info(f"🔧 Cấu hình: Model={settings.MODEL_NAME}, Max Tokens={settings.MAX_INPUT_TOKENS}")