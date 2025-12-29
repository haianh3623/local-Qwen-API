import io
import os
import logging
import re
import fitz  # PyMuPDF
import aiofiles
from fastapi import UploadFile
from fastapi.concurrency import run_in_threadpool
from docx import Document

# IMPORT SERVICE BẢO MẬT (Giả sử file prompt_security_service.py nằm cùng thư mục)
from app.services.prompt_security_service import PromptSecurityService

logger = logging.getLogger("file_parser")
logger.setLevel(logging.INFO)

class FileParserService:
    def __init__(self):
        # Pre-compile regex để tối ưu hiệu năng
        self.pattern_whitespace = re.compile(r'\s+')
        self.pattern_paragraphs = re.compile(r'\n\s*\n')
        self.pattern_newlines = re.compile(r'\n+')
        
        # --- TÍCH HỢP BẢO MẬT ---
        # Khởi tạo security service một lần duy nhất
        self.security_service = PromptSecurityService()

    def _clean_text(self, text: str) -> str:
        if not text: return ""
        
        # Chuẩn hóa khoảng trắng cơ bản
        text = text.replace('\t', ' ').replace('\u00a0', ' ')
        
        # Tách đoạn văn bản dựa trên dòng trống
        paragraphs = self.pattern_paragraphs.split(text)
        cleaned_paragraphs = []
        
        for p in paragraphs:
            # Nối các dòng bị ngắt trong cùng 1 đoạn, xóa khoảng trắng thừa
            clean_p = self.pattern_newlines.sub(' ', p).strip()
            clean_p = self.pattern_whitespace.sub(' ', clean_p)
            if clean_p:
                cleaned_paragraphs.append(clean_p)
                
        return "\n\n".join(cleaned_paragraphs)

    def _format_response(self, filename: str, content: str, error_msg: str = None) -> str:
        # Xử lý tên file để tránh phá vỡ XML attribute
        safe_filename = filename.replace('"', '').replace('<', '').replace('>', '')
        
        if error_msg:
            return f'<file_attachment name="{safe_filename}">\n[SYSTEM ERROR: {error_msg}]\n</file_attachment>'
            
        # Lưu ý: content ở đây đã được Sanitize (escape HTML) bởi security service
        return f'<file_attachment name="{safe_filename}">\n{content}\n</file_attachment>'

    def _parse_pdf(self, content_bytes: bytes) -> str:
        text = ""
        # fitz mở file từ memory cực nhanh và an toàn
        with fitz.open(stream=content_bytes, filetype="pdf") as doc:
            for page in doc:
                # flags=~fitz.TEXT_PRESERVE_IMAGES giúp bỏ qua ảnh, tránh lỗi crash
                text += page.get_text(sort=True) + "\n"
        return text

    def _parse_docx(self, content_bytes: bytes) -> str:
        doc = Document(io.BytesIO(content_bytes))
        return "\n".join([para.text for para in doc.paragraphs])

    def _process_content_sync(self, content_bytes: bytes, filename: str) -> str:
        """Hàm xử lý logic nặng (CPU bound), sẽ chạy trong thread pool"""
        filename = filename.lower()
        raw_text = ""
        
        try:
            if filename.endswith((".txt", ".md", ".py", ".java", ".cpp", ".json", ".html", ".css", ".js", ".php")):
                raw_text = content_bytes.decode("utf-8", errors="ignore")
            
            elif filename.endswith(".pdf"):
                raw_text = self._parse_pdf(content_bytes)
                if not raw_text.strip():
                    raise ValueError("PDF không chứa văn bản (có thể là file scan/ảnh)")

            elif filename.endswith(".docx"):
                raw_text = self._parse_docx(content_bytes)
            
            else:
                return self._format_response(filename, "", "Định dạng file không được hỗ trợ")

            # 1. Làm sạch cơ bản (xóa khoảng trắng thừa)
            cleaned_text = self._clean_text(raw_text)
            
            # --- BƯỚC BẢO MẬT QUAN TRỌNG ---
            # 2. Quét Injection & Vệ sinh HTML tags (Sanitize)
            # Hàm này sẽ trả về văn bản sạch (đã escape < >) hoặc thông báo lỗi nếu gian lận
            safe_text = self.security_service.validate_and_sanitize(cleaned_text)
            
            # 3. Đóng gói vào XML (Lúc này safe_text đã an toàn để nhúng vào XML)
            return self._format_response(filename, safe_text, None)

        except Exception as e:
            logger.error(f"Error parsing {filename}: {e}")
            return self._format_response(filename, "", str(e))

    async def parse_upload_file(self, file: UploadFile) -> str:
        if not file: return ""
        try:
            content = await file.read()
            # Đẩy việc xử lý nặng sang thread khác để không chặn API
            result = await run_in_threadpool(self._process_content_sync, content, file.filename)
            await file.seek(0)
            return result
        except Exception as e:
            return self._format_response(file.filename, "", str(e))

    async def parse_local_file(self, file_path: str) -> str:
        if not os.path.exists(file_path):
            return ""
        filename = os.path.basename(file_path)
        try:
            async with aiofiles.open(file_path, mode='rb') as f:
                content = await f.read()
            # Tái sử dụng logic qua thread pool
            return await run_in_threadpool(self._process_content_sync, content, filename)
        except Exception as e:
            return self._format_response(filename, "", f"Lỗi đọc file local: {str(e)}")

file_parser = FileParserService()