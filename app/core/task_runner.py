import httpx
import logging
import asyncio
from typing import Callable, Any, Dict
from app.core.config import settings

logger = logging.getLogger("task_runner")
# Bỏ dòng logging.basicConfig() ở đây nếu đã config tập trung ở main.py

global_semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_REQUESTS)

class TaskRunner:
    @staticmethod
    async def run_task_and_callback(
        processing_function: Callable,
        input_data: Dict[str, Any],
        callback_url: str,
        request_id: str
    ):
        logger.info(f"⏳ [Queue] Request {request_id} đang chờ slot...")
        
        async with global_semaphore:
            logger.info(f"🔄 [Processing] Đang xử lý {request_id}...")
            
            response_payload = {
                "status": "error",
                "score": 0,
                "feedback": None,
                "error": None
                # model_used sẽ được thêm sau nếu thành công
            }

            try:
                # 1. Chạy logic
                result = await processing_function(input_data)
                
                if hasattr(result, "ai_model") and result.ai_model:
                    response_payload["model_used"] = result.ai_model

                if result.error:
                    response_payload["status"] = "error"
                    response_payload["error"] = result.error
                    response_payload["score"] = 0
                    response_payload["feedback"] = None
                else:
                    response_payload["status"] = "success"
                    response_payload["score"] = result.score
                    response_payload["feedback"] = result.feedback
                    response_payload["error"] = None
                    if not response_payload.get("model_used"):
                         response_payload["model_used"] = settings.MODEL_NAME

            except Exception as e:
                logger.error(f"Task failed: {e}")
                response_payload["status"] = "error"
                response_payload["error"] = f"Lỗi hệ thống: {str(e)}"
                response_payload["score"] = 0

            # 3. Gửi Callback với Header xác thực
            try:
                logger.info(f"🚀 [Callback] Gửi về: {callback_url}")
                
                # [MỚI] Chuẩn bị Header theo chuẩn Bearer
                headers = {}
                if settings.SHARED_SECRET_KEY:
                    # Format chuẩn: "Bearer <token>"
                    headers["Authorization"] = f"Bearer {settings.SHARED_SECRET_KEY}"
                
                async with httpx.AsyncClient(timeout=30.0) as client:
                    await client.post(
                        callback_url, 
                        json=response_payload,
                        headers=headers # Gửi header đi
                    )
                logger.info(f"✅ [Done] Hoàn tất {request_id}")
            except Exception as e:
                logger.error(f"❌ [Callback Error] Không thể gọi Moodle: {e}")

task_runner = TaskRunner()