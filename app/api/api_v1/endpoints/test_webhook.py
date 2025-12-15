from fastapi import APIRouter, Request, HTTPException
from typing import Dict, Any
import logging

router = APIRouter()
logger = logging.getLogger("mock_moodle")
logger.setLevel(logging.INFO)

# --- KHO CHỨA TẠM THỜI (MEMORY DB) ---
# Dùng để lưu kết quả AI gửi về, giúp script test có thể query được
RECEIVED_CALLBACKS: Dict[str, Any] = {}

@router.post("/mock-moodle-callback")
async def receive_callback(request: Request):
    """
    [MOCK MOODLE] Nhận kết quả từ TaskRunner gửi về.
    """
    data = await request.json()
    req_id = data.get("request_id")
    
    # In ra log để bạn thấy ngay lập tức
    print("\n" + "="*40)
    print(f"📬 [MOCK MOODLE LOG] Đã nhận Callback cho ID: {req_id}")
    print(f"   Status: {data.get('status')}")
    print(f"   Score:  {data.get('score')}")
    print("="*40 + "\n")
    
    # LƯU VÀO RAM
    if req_id:
        RECEIVED_CALLBACKS[req_id] = data
    
    return {"status": "received"}

# --- [PHẦN BẠN ĐANG THIẾU] ---
@router.get("/check-result/{request_id}")
async def check_result(request_id: str):
    """
    API để Test Script gọi vào kiểm tra xem ID này đã chấm xong chưa.
    """
    # Kiểm tra trong RAM xem có ID này chưa
    if request_id in RECEIVED_CALLBACKS:
        return {
            "status": "done",
            "data": RECEIVED_CALLBACKS[request_id]
        }
    else:
        # Nếu chưa có, trả về pending để script test đợi tiếp
        return {"status": "pending", "message": "Chưa có kết quả"}