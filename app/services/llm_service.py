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
from app.services.token_service import token_service

# Cấu hình logger để theo dõi quá trình retry
logger = logging.getLogger("ai_engine")
logger.setLevel(logging.INFO)

class LLMService:
    def __init__(self):
        self.base_url = settings.OLLAMA_HOST
        self.model = settings.MODEL_NAME

    # --- HÀM CORE: Gửi Request có cơ chế Retry ---
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.ReadTimeout)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    async def _call_ollama(self, payload: dict) -> dict:
        # Kiểm tra token
        check = token_service.check_token_limit(payload.get("prompt", ""))
        if not check["is_valid"]:
            raise ValueError(f"Token quá dài: {check['count']}/{check['limit']}")

        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(f"{self.base_url}/api/generate", json=payload)
            response.raise_for_status()
            return response.json()
        
    async def test_llm_response(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.5}
        }
        result = await self._call_ollama_api(payload)
        return result.get("response", "").strip()

    # --- CHỨC NĂNG 1: Chấm điểm bài làm ---
    async def grade_submission(self, data: dict) -> GradingResponse:
        """
        Thực hiện chấm điểm 1 bài.
        Input: data (dict) chứa question, submission, rubric...
        Output: GradingResponse object
        """
        # 1. Tạo Prompt
        prompt = prompt_service.build_grading_prompt(
            question=data['question'],
            submission=data['submission'],
            max_score=data['max_score'],
            reference=data.get('reference'),
            rubric=data.get('rubric'),
            teacher_instruction=data.get('teacher_instruction')
        )
        
        # 2. Cấu hình gửi đi
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.1, "num_ctx": 4096}
        }

        try:
            # 3. Gọi AI
            result = await self._call_ollama(payload)
            
            # 4. Parse kết quả
            ai_content = json.loads(result.get("response", "{}"))
            
            # Ép kiểu điểm số an toàn
            raw_score = float(ai_content.get("score", 0))
            final_score = min(raw_score, float(data['max_score']))

            return GradingResponse(
                score=final_score,
                feedback=ai_content.get("feedback", "Không có nhận xét"),
                ai_model=self.model,
                error=None
            )

            # return GradingResponse(
            #     score=8.0,
            #     feedback="Bài làm tốt, đáp ứng yêu cầu đề bài.",
            #     ai_model=self.model,
            #     error=None
            # )

        except ValueError as ve:
            # Lỗi do token quá dài (Logic nghiệp vụ)
            return GradingResponse(score=None, feedback=None, error=str(ve), ai_model=self.model)
        except Exception as e:
            # Lỗi hệ thống (Mạng, Code...)
            return GradingResponse(score=None, feedback=None, error=f"AI Error: {str(e)}", ai_model=self.model)

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