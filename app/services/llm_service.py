import httpx
import json
import logging
import re
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)
from app.core.config import settings
# Lưu ý: Import đúng file schema đã tạo ở bước trước
from app.schemas.grading import GradingResponse
from app.services.prompt_service import prompt_service
from app.services.token_service import token_service

# Cấu hình logger
logger = logging.getLogger("ai_engine")
logger.setLevel(logging.INFO)

class LLMService:
    def __init__(self):
        self.base_url = settings.OLLAMA_HOST
        self.model = settings.MODEL_NAME

    # --- HÀM HELPER: Làm sạch chuỗi JSON từ AI ---
    def _clean_json_string(self, json_str: str) -> str:
        """
        Loại bỏ các ký tự markdown như ```json ... ``` nếu AI lỡ trả về.
        """
        json_str = json_str.strip()
        # Nếu bắt đầu bằng ```json hoặc ```
        if json_str.startswith("```"):
            # Dùng regex để lấy nội dung bên trong block code
            match = re.search(r"```(?:json)?(.*?)```", json_str, re.DOTALL)
            if match:
                return match.group(1).strip()
        return json_str

    # --- HÀM CORE: Gửi Request có cơ chế Retry ---
    @retry(
        stop=stop_after_attempt(3), # Thử tối đa 3 lần
        wait=wait_exponential(multiplier=1, min=2, max=10), # Chờ tăng dần: 2s, 4s, 8s
        retry=retry_if_exception_type((httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    async def _call_ollama_api(self, payload: dict) -> dict:
        # 1. Kiểm tra Token limit trước khi gửi để tiết kiệm tài nguyên
        # Lấy prompt ra để đếm (chấp nhận payload có thể không có prompt nếu là chat mode)
        prompt_text = payload.get("prompt", "")
        if prompt_text:
            check = token_service.check_token_limit(prompt_text)
            if not check["is_valid"]:
                raise ValueError(f"Token limit exceeded: {check['count']}/{check['limit']}")

        # 2. Gửi Request
        async with httpx.AsyncClient(timeout=120.0) as client: # Tăng timeout lên 120s cho AI suy nghĩ
            try:
                response = await client.post(f"{self.base_url}/api/generate", json=payload)
                response.raise_for_status() # Bắt lỗi 4xx, 5xx
                return response.json()
            except httpx.HTTPStatusError as exc:
                # Log lỗi cụ thể từ Server Ollama nếu có
                logger.error(f"Ollama API Error: {exc.response.text}")
                raise exc

    # --- CHỨC NĂNG 1: Chấm điểm bài làm ---
    async def grade_submission(self, data: dict) -> GradingResponse:
        """
        Thực hiện chấm điểm 1 bài.
        Input: data (dict) chứa question, submission, rubric...
        Output: GradingResponse object
        """
        try:
            # 1. Tạo Prompt (Logic nằm ở prompt_service để code gọn)
            prompt = prompt_service.build_grading_prompt(
                course_id=data.get('course_id'),
                question=data['question'],
                submission=data['submission'],
                max_score=data['max_score'],
                reference=data.get('reference'),
                rubric=data.get('rubric'),
                teacher_instruction=data.get('teacher_instruction')
            )

            # return GradingResponse(
            #     score=80,
            #     feedback="Bài làm tốt, nhưng cần cải thiện phần lập luận.",
            #     ai_model=self.model,
            #     error=None
            # )
            
            # 2. Cấu hình payload
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "format": "json", # Bắt buộc AI trả về JSON
                "options": {
                    "temperature": 0.1, # Thấp để chấm điểm ổn định
                    "num_ctx": 4096     # Context window
                }
            }

            # 3. Gọi AI (Có retry)
            result = await self._call_ollama_api(payload)
            
            # 4. Parse kết quả
            raw_response = result.get("response", "{}")
            cleaned_response = self._clean_json_string(raw_response)
            
            try:
                ai_content = json.loads(cleaned_response)
            except json.JSONDecodeError:
                return GradingResponse(
                    score=None, 
                    feedback=raw_response, # Trả về text gốc để debug
                    error="AI trả về format không phải JSON hợp lệ.", 
                    ai_model=self.model
                )
            
            # 5. Xử lý Logic điểm số (Min/Max)
            # Dùng .get(..., 0) để tránh lỗi nếu AI quên field score
            raw_score = float(ai_content.get("score", 0))
            max_allowed = float(data.get('max_score', 10))
            
            # Đảm bảo điểm không vượt quá max_score
            final_score = min(raw_score, max_allowed)

            # 6. Trả về Object chuẩn
            return GradingResponse(
                score=final_score,
                feedback=ai_content.get("feedback", "Không có nhận xét chi tiết."),
                ai_model=self.model,
                error=None
            )

        except ValueError as ve:
            # Lỗi do Logic (VD: Token quá dài)
            logger.error(f"Validation Error: {ve}")
            return GradingResponse(score=0, feedback=None, error=str(ve), ai_model=self.model)
            
        except Exception as e:
            # Lỗi hệ thống không mong muốn
            logger.error(f"System Error in Grading: {e}", exc_info=True)
            return GradingResponse(score=0, feedback=None, error=f"Internal Error: {str(e)}", ai_model=self.model)

    # --- CHỨC NĂNG 2: Làm phẳng Rubric ---
    async def flatten_rubric(self, rubric_type: str, raw_data: dict, context: str) -> str:
        try:
            prompt = prompt_service.build_rubric_flattening_prompt(rubric_type, raw_data, context)
            
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.3} # Hơi sáng tạo một chút để diễn giải rubric
            }

            # Gọi hàm dùng chung _call_ollama_api
            result = await self._call_ollama_api(payload)
            return result.get("response", "").strip()

        except Exception as e:
            logger.error(f"Failed to flatten rubric: {e}")
            return f"Lỗi xử lý Rubric: {str(e)}"

    # --- CHỨC NĂNG 3: Test kết nối đơn giản ---
    async def test_llm_response(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False
        }
        try:
            result = await self._call_ollama_api(payload)
            return result.get("response", "").strip()
        except Exception as e:
            return f"Error: {str(e)}"

llm_service = LLMService()