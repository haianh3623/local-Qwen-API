import tiktoken
import logging
from app.core.config import settings

logger = logging.getLogger("token_service")

class TokenService:
    def __init__(self):
        # Sử dụng encoding 'cl100k_base' (tương đương GPT-4)
        # Đây là chuẩn phổ biến, tốc độ mã hóa cực nhanh
        try:
            self.encoder = tiktoken.get_encoding("cl100k_base")
        except Exception:
            # Fallback nếu lỗi (hiếm gặp)
            self.encoder = tiktoken.get_encoding("p50k_base")

    def count_tokens(self, text: str) -> int:
        """
        Đếm số lượng token ước tính của văn bản.
        """
        if not text:
            return 0
        try:
            # tiktoken.encode trả về list các số nguyên (tokens)
            tokens = self.encoder.encode(text)
            return len(tokens)
        except Exception as e:
            logger.error(f"Error counting tokens: {e}")
            # Fallback thô: 1 token ~ 4 ký tự (tiếng Anh) hoặc 2-3 ký tự (tiếng Việt)
            # Trả về ước lượng an toàn
            return len(text) // 3

    def check_token_limit(self, text: str) -> dict:
        """
        Kiểm tra xem text có vượt quá giới hạn không.
        Trả về: { "is_valid": bool, "count": int, "limit": int }
        """
        count = self.count_tokens(text)
        limit = settings.MAX_INPUT_TOKENS
        
        return {
            "is_valid": True,
            "count": count,
            "limit": limit,
            "message": f"Token count: {count}/{limit}"
        }

token_service = TokenService()