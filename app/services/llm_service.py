import httpx
import json
import logging
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)
from app.core.config import settings
from app.schemas.grading import GradingResponse
from app.services.prompt_service import prompt_service

# Cấu hình logger để theo dõi quá trình retry
logger = logging.getLogger("ai_engine")
logging.basicConfig(level=logging.INFO)

class LLMService:
    def __init__(self):
        self.base_url = settings.OLLAMA_HOST
        self.model = settings.MODEL_NAME

    # --- HÀM CORE: Gửi Request có cơ chế Retry ---
    @retry(
        # 1. Điều kiện dừng: Thử tối đa 3 lần
        stop=stop_after_attempt(3),
        
        # 2. Chiến thuật chờ: Exponential Backoff 
        # (Lần 1 chờ 1s, Lần 2 chờ 2s, tăng dần tối đa 10s)
        wait=wait_exponential(multiplier=1, min=1, max=10),
        
        # 3. Chỉ retry khi gặp các lỗi mạng cụ thể (Không retry lỗi logic code)
        retry=retry_if_exception_type((httpx.ConnectError, httpx.ReadTimeout, httpx.PoolTimeout, httpx.RemoteProtocolError)),
        
        # 4. Ghi log mỗi khi retry để debug
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    async def _call_ollama_api(self, payload: dict) -> dict:
        """
        Hàm nội bộ chịu trách nhiệm gọi API Ollama.
        Được bảo vệ bởi @retry.
        """
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(f"{self.base_url}/api/generate", json=payload)
            response.raise_for_status()
            return response.json()

    # --- CHỨC NĂNG 1: Chấm điểm bài làm ---
    async def grade_comprehensive(self, data: dict) -> GradingResponse:
        # 1. Tạo Prompt
        prompt = prompt_service.build_grading_prompt(
            data['question'], data['submission'], data['max_score'],
            data.get('reference'), data.get('rubric'), data.get('teacher_instruction')
        )
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.1, "num_ctx": 4096}
        }

        try:
            # Gọi API
            result = await self._call_ollama_api(payload)
            
            # Xử lý kết quả thành công
            ai_text = result.get("response", "{}")
            ai_content = json.loads(ai_text)
            
            raw_score = float(ai_content.get("score", 0))
            final_score = min(raw_score, float(data['max_score']))

            return GradingResponse(
                score=final_score,
                feedback=ai_content.get("feedback", "Không có nhận xét"),
                model_used=self.model,
                error=None # Không có lỗi
            )

        except ValueError as ve:
            # [CASE 1] LỖI TOKEN QUÁ DÀI -> Trả về NULL + Log lỗi
            return GradingResponse(
                score=None,    # <--- Trả về NULL
                feedback=None, # <--- Trả về NULL
                error=f"[Token Limit Error] {str(ve)}", # <--- Gửi log lỗi
                model_used=self.model
            )
            
        except Exception as e:
            # [CASE 2] LỖI KẾT NỐI API / TIMEOUT -> Trả về NULL + Log lỗi
            logger.error(f"Grading failed: {e}")
            return GradingResponse(
                score=None,    # <--- Trả về NULL
                feedback=None, # <--- Trả về NULL
                error=f"[API Connection Error] Hệ thống không phản hồi. Chi tiết: {str(e)}", # <--- Gửi log lỗi
                model_used=self.model
            )

    # --- CHỨC NĂNG 2: Làm phẳng Rubric ---
    async def flatten_rubric(self, rubric_type: str, raw_data: dict, context: str) -> str:
        prompt = prompt_service.build_rubric_flattening_prompt(rubric_type, raw_data, context)
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.3}
        }

        try:
            # Gọi hàm có retry
            result = await self._call_ollama_api(payload)
            return result.get("response", "").strip()

        except Exception as e:
            logger.error(f"Failed to flatten rubric after retries: {e}")
            return f"Lỗi xử lý Rubric: Hệ thống AI không phản hồi ({str(e)})"

llm_service = LLMService()