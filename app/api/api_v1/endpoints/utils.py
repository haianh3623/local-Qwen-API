from fastapi import APIRouter
from pydantic import BaseModel
from app.services.llm_service import llm_service # Import service vừa tạo
from app.core.config import settings
import httpx

router = APIRouter()

@router.get("/test-connection")
async def test_system_connection():
    """
    API này dùng để kiểm tra sức khỏe hệ thống:
    1. Kiểm tra API FastAPI có hoạt động không.
    2. Kiểm tra kết nối từ FastAPI sang Ollama (Internal Docker Network).
    """
    
    # 1. Thông tin của API hiện tại
    result = {
        "fastapi_status": "ok",
        "message": "FastAPI is running successfully",
        "ollama_connection": "checking..."
    }

    # 2. Thử gọi sang Ollama (Bên trong mạng Docker)
    try:
        # Gọi endpoint gốc của Ollama (thường trả về "Ollama is running")
        # settings.OLLAMA_HOST lấy từ .env (ví dụ: http://ollama:11434)
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{settings.OLLAMA_HOST}/", timeout=5.0)
            
        if response.status_code == 200:
            result["ollama_connection"] = "success"
            result["ollama_message"] = response.text.strip() # Thường là "Ollama is running"
        else:
            result["ollama_connection"] = "error"
            result["ollama_status_code"] = response.status_code

    except Exception as e:
        result["ollama_connection"] = "failed"
        result["error_detail"] = f"Không thể kết nối tới {settings.OLLAMA_HOST}. Lỗi: {str(e)}"
        # Gợi ý lỗi thường gặp
        result["hint"] = "Kiểm tra xem container Ollama có đang chạy cùng network 'internal_net' không."

    return result

class QuestionRequest(BaseModel):
    question: str # Đây là trường để bạn nhập câu hỏi

@router.post("/ask-llm")
async def ask_llm(request: QuestionRequest):
    """
    API test gửi câu hỏi cho model Qwen2.5.
    Nhập câu hỏi vào field 'question'.
    """
    # Gọi service để lấy câu trả lời
    answer = await llm_service.test_llm_response(request.question)
    
    return {
        "your_question": request.question,
        "model_used": settings.MODEL_NAME,
        "answer": answer
    }