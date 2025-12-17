import httpx
import logging
import asyncio
from datetime import datetime
from typing import Callable, Any, Dict
from app.core.config import settings
from app.schemas.grading import GradingResponse, WebhookPayload

# Setup Logger
logger = logging.getLogger("task_runner")

# Giới hạn số lượng task chạy đồng thời
global_semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_REQUESTS)

class TaskRunner:
    """
    Class chịu trách nhiệm điều phối:
    1. Kiểm soát concurrency (Semaphore).
    2. Gọi hàm xử lý (Business Logic).
    3. Đóng gói kết quả chuẩn Schema.
    4. Gửi Webhook (kèm cơ chế Retry).
    """

    async def run_task_and_callback(
        self,
        processing_function: Callable[[Any], GradingResponse], # Hàm này bắt buộc trả về GradingResponse
        input_data: Dict[str, Any],
        callback_url: str,
        request_id: str
    ):
        # return True
        logger.info(f"⏳ [Queue] Request {request_id} đang chờ slot xử lý...")
        
        async with global_semaphore:
            logger.info(f"▶️ [Start] Bắt đầu xử lý {request_id}")
            
            try:
                # 1. Thực thi Logic chính (AI Grading)
                # Lưu ý: Hàm processing_function phải trả về object GradingResponse
                result: GradingResponse = await processing_function(input_data)
                
                # 2. Kiểm tra kết quả logic
                if result.error:
                    status = "error"
                    logger.warning(f"⚠️ [Logic Error] {request_id}: {result.error}")
                else:
                    status = "success"
                    logger.info(f"✅ [Success] {request_id} - Score: {result.score}")

                # 3. Đóng gói Payload thành công
                payload = WebhookPayload(
                    request_id=request_id,
                    status=status,
                    timestamp=datetime.utcnow().isoformat(),
                    data=result
                )

            except Exception as e:
                # 4. Xử lý lỗi hệ thống (Crash code, AI service down, v.v.)
                logger.error(f"❌ [System Error] {request_id}: {str(e)}", exc_info=True)
                
                # Tạo payload báo lỗi hệ thống
                payload = WebhookPayload(
                    request_id=request_id,
                    status="error",
                    timestamp=datetime.utcnow().isoformat(),
                    data=None,
                    system_error=f"Internal Server Error: {str(e)}"
                )

        # 5. Gửi Webhook (Nằm ngoài Semaphore để giải phóng slot xử lý sớm)
        await self._send_webhook_with_retry(callback_url, payload)

    async def _send_webhook_with_retry(self, url: str, payload: WebhookPayload, max_retries: int = 3):
        """
        Gửi webhook với cơ chế thử lại (Retry) nếu thất bại.
        """
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "FastAPI-Grader/1.0"
        }
        
        # Thêm bảo mật Bearer Token nếu có cấu hình
        if settings.SHARED_SECRET_KEY:
            headers["Authorization"] = f"Bearer {settings.SHARED_SECRET_KEY}"

        print("Secret key ", settings.SHARED_SECRET_KEY[:5])

        # Chuyển Pydantic model sang Dict
        json_body = payload.model_dump()

        async with httpx.AsyncClient(timeout=30.0) as client:
            for attempt in range(1, max_retries + 1):
                try:
                    logger.info(f"🚀 [Callback] Gửi tới {url} (Lần {attempt})")
                    response = await client.post(url, json=json_body, headers=headers)
                    
                    # Nếu status code là 2xx (200, 201, 202...)
                    if response.is_success:
                        logger.info(f"✅ [Callback Done] Webhook nhận thành công: {response.status_code}")
                        return
                    else:
                        logger.warning(f"⚠️ [Callback Fail] Server trả về {response.status_code}. Thử lại...")

                except httpx.RequestError as e:
                    logger.warning(f"⚠️ [Callback Network Error] Lỗi mạng: {e}. Thử lại...")
                
                # Chờ tăng dần trước khi thử lại (Exponential Backoff: 2s, 4s, 8s...)
                if attempt < max_retries:
                    sleep_time = 2 ** attempt
                    await asyncio.sleep(sleep_time)

        logger.error(f"❌ [Callback GiveUp] Đã thử {max_retries} lần nhưng thất bại. Request ID: {payload.request_id}")

# Khởi tạo singleton
task_runner = TaskRunner()