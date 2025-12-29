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
        Loại bỏ các ký tự markdown như ```json ... ``` để tránh lỗi parse.
        """
        json_str = json_str.strip()
        if json_str.startswith("```"):
            match = re.search(r"```(?:json)?(.*?)```", json_str, re.DOTALL)
            if match:
                return match.group(1).strip()
        return json_str

    # --- CORE 1: Hàm xử lý JSON (Có Retry cả Mạng + Format JSON) ---
    # Dùng cho: Chấm điểm, Trích xuất thông tin cấu trúc
    @retry(
        stop=stop_after_attempt(3), # Thử tối đa 3 lần
        wait=wait_exponential(multiplier=1, min=2, max=10),
        # Retry nếu: Mất mạng, Timeout, Server lỗi (500), HOẶC JSON lỗi
        retry=retry_if_exception_type((
            httpx.ConnectError, 
            httpx.ReadTimeout, 
            httpx.ConnectTimeout, 
            httpx.HTTPStatusError,
            json.JSONDecodeError 
        )),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    async def _generate_json_with_retry(self, payload: dict) -> dict:
        """
        Gửi request và ép buộc trả về dict hợp lệ. 
        Nếu parse lỗi -> Ném ngoại lệ -> Tenacity bắt -> Retry lại từ đầu.
        """
        # 1. Kiểm tra Token limit
        prompt_text = payload.get("prompt", "")
        if prompt_text:
            check = token_service.check_token_limit(prompt_text)
            if not check["is_valid"]:
                # Token quá lớn thì không retry làm gì, ném lỗi thẳng
                raise ValueError(f"Token limit exceeded: {check['count']}/{check['limit']}")

        # 2. Gửi Request
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(f"{self.base_url}/api/generate", json=payload)
            response.raise_for_status() # Ném lỗi nếu status code >= 400
            result = response.json()

        # 3. Parse JSON (Điểm mấu chốt: Nếu lỗi ở đây, hàm sẽ retry lại bước 2)
        raw_response = result.get("response", "{}")
        cleaned_response = self._clean_json_string(raw_response)
        
        # Nếu dòng này lỗi JSONDecodeError -> Tenacity sẽ kích hoạt retry
        return json.loads(cleaned_response)

    # --- CORE 2: Hàm xử lý Text thường (Chỉ Retry Mạng) ---
    # Dùng cho: Chat, Làm phẳng Rubric, Tóm tắt
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.ReadTimeout, httpx.HTTPStatusError)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    async def _generate_text_with_retry(self, payload: dict) -> str:
        # Kiểm tra token
        prompt_text = payload.get("prompt", "")
        if prompt_text:
            check = token_service.check_token_limit(prompt_text)
            if not check["is_valid"]:
                raise ValueError(f"Token limit exceeded: {check['count']}/{check['limit']}")

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(f"{self.base_url}/api/generate", json=payload)
            response.raise_for_status()
            result = response.json()
            
        return result.get("response", "").strip()

    # --- CHỨC NĂNG 1: Chấm điểm bài làm (Dùng Core 1) ---
    async def grade_submission(self, data: dict) -> GradingResponse:
        try:
            # 1. Tạo Prompt
            prompt = prompt_service.build_grading_prompt(
                course_id=data.get('course_id'),
                question=data['question'],
                submission=data['submission'],
                max_score=data['max_score'],
                reference=data.get('reference'),
                rubric=data.get('rubric'),
                teacher_instruction=data.get('teacher_instruction')
            )

            # 2. Cấu hình payload
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "format": "json", # Bắt buộc JSON mode của Ollama
                "options": {
                    "temperature": 0.1,
                    "num_ctx": 4096
                }
            }

            # 3. Gọi hàm có Retry JSON (Core 1)
            # Không cần try-catch JSONDecodeError ở đây nữa vì Core 1 đã lo rồi
            # Nếu Core 1 vẫn fail sau 3 lần, nó sẽ ném lỗi ra ngoài -> vào except Exception bên dưới
            ai_content = await self._generate_json_with_retry(payload)
            
            # 4. Xử lý Logic điểm số
            raw_score = float(ai_content.get("score", 0))
            max_allowed = float(data.get('max_score', 10))
            final_score = min(raw_score, max_allowed)

            return GradingResponse(
                score=final_score,
                feedback=ai_content.get("feedback", "Không có nhận xét chi tiết."),
                ai_model=self.model,
                error=None
            )

        except ValueError as ve:
            # Lỗi Token quá lớn hoặc lỗi logic
            logger.error(f"Validation Error: {ve}")
            return GradingResponse(score=0, feedback=None, error=str(ve), ai_model=self.model)
            
        except json.JSONDecodeError:
            # Lỗi này chỉ xảy ra nếu sau 3 lần retry mà AI vẫn trả về rác
            logger.error("Failed to parse JSON after retries")
            return GradingResponse(
                score=0, 
                feedback=None, 
                error="AI Error: Could not generate valid JSON format after multiple attempts.", 
                ai_model=self.model
            )

        except Exception as e:
            # Các lỗi hệ thống khác
            logger.error(f"System Error in Grading: {e}", exc_info=True)
            return GradingResponse(score=0, feedback=None, error=f"Internal Error: {str(e)}", ai_model=self.model)

    # --- CHỨC NĂNG 2: Làm phẳng Rubric (Dùng Core 2) ---
    async def flatten_rubric(self, rubric_type: str, raw_data: dict, context: str) -> str:
        try:
            prompt = prompt_service.build_rubric_flattening_prompt(rubric_type, raw_data, context)
            
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.3}
            }

            # Dùng hàm Core 2 (chỉ trả về text)
            return await self._generate_text_with_retry(payload)

        except Exception as e:
            logger.error(f"Failed to flatten rubric: {e}")
            return f"Lỗi xử lý Rubric: {str(e)}"

    # --- CHỨC NĂNG 3: Test kết nối ---
    async def test_llm_response(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False
        }
        try:
            return await self._generate_text_with_retry(payload)
        except Exception as e:
            return f"Error: {str(e)}"

# Khởi tạo instance singleton
llm_service = LLMService()