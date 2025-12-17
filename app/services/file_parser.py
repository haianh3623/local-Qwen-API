import io
import os
import logging
import re
import aiofiles
from fastapi import UploadFile
from pypdf import PdfReader
from docx import Document

# Cấu hình logging
logger = logging.getLogger("file_parser")
logger.setLevel(logging.INFO)

class FileParserService:
    def _clean_text(self, text: str) -> str:
        """
        Làm sạch văn bản: nối các dòng bị ngắt quãng, xóa ký tự lạ.
        """
        if not text: return ""

        # 1. Thay thế các khoảng trắng đặc biệt
        text = text.replace('\t', ' ').replace('\u00a0', ' ')

        # 2. Xử lý lỗi "mỗi từ một dòng" của PDF
        paragraphs = re.split(r'\n\s*\n', text)
        
        cleaned_paragraphs = []
        for p in paragraphs:
            clean_p = re.sub(r'\n+', ' ', p).strip()
            clean_p = re.sub(r'\s+', ' ', clean_p)
            if clean_p:
                cleaned_paragraphs.append(clean_p)
        
        return "\n\n".join(cleaned_paragraphs)

    def _format_response(self, filename: str, content: str, error_msg: str = None) -> str:
        """
        Đóng gói kết quả vào thẻ XML.
        """
        safe_filename = filename.replace('"', '').replace('<', '').replace('>', '')
        
        if error_msg:
            return f"""
<file_attachment name="{safe_filename}">
[SYSTEM ERROR: {error_msg}]
</file_attachment>
"""
        return f"""
<file_attachment name="{safe_filename}">
{content}
</file_attachment>
"""

    def _extract_text_from_bytes(self, content_bytes: bytes, filename: str) -> str:
        """
        Logic cốt lõi: Chuyển đổi bytes thành text dựa trên đuôi file.
        Trả về: (text_content, error_message)
        """
        filename = filename.lower()
        file_text = ""

        try:
            # --- CASE 1: FILE TEXT ---
            if filename.endswith((".txt", ".md", ".json", ".py", ".php", ".html", ".css", ".js", ".java", ".cpp")):
                return self._clean_text(content_bytes.decode("utf-8", errors="ignore")), None

            # --- CASE 2: FILE PDF ---
            elif filename.endswith(".pdf"):
                try:
                    pdf_reader = PdfReader(io.BytesIO(content_bytes))
                    for page in pdf_reader.pages:
                        try:
                            text = page.extract_text(extraction_mode="layout")
                        except:
                            text = page.extract_text()
                        if text:
                            file_text += text + "\n"
                    
                    if not file_text.strip():
                        return "", "File PDF này không chứa văn bản (có thể là file scan/ảnh)."
                    
                    return self._clean_text(file_text), None
                except Exception as pdf_err:
                    return "", f"Lỗi đọc PDF: {str(pdf_err)}"

            # --- CASE 3: FILE WORD ---
            elif filename.endswith(".docx"):
                try:
                    doc = Document(io.BytesIO(content_bytes))
                    for para in doc.paragraphs:
                        file_text += para.text + "\n"
                    return self._clean_text(file_text), None
                except Exception as docx_err:
                    return "", f"Lỗi đọc DOCX: {str(docx_err)}"
            
            # --- CASE 4: KHÔNG HỖ TRỢ ---
            else:
                return "", "Định dạng file không được hỗ trợ."

        except Exception as e:
            logger.error(f"Critical error parsing {filename}: {e}")
            return "", f"Critical Parsing Error: {str(e)}"

    async def parse_upload_file(self, file: UploadFile) -> str:
        """
        Xử lý file từ UploadFile (API Form Data)
        """
        if not file: return ""
        try:
            content_bytes = await file.read()
            text, error = self._extract_text_from_bytes(content_bytes, file.filename)
            
            # Reset con trỏ file sau khi đọc
            await file.seek(0)
            
            return self._format_response(file.filename, text, error)
        except Exception as e:
            return self._format_response(file.filename, "", str(e))

    async def parse_local_file(self, file_path: str) -> str:
        """
        Xử lý file từ đường dẫn cứng trên server
        """
        if not os.path.exists(file_path):
            return ""
        
        filename = os.path.basename(file_path)
        try:
            # Đọc file dưới dạng binary
            async with aiofiles.open(file_path, mode='rb') as f:
                content_bytes = await f.read()
            
            text, error = self._extract_text_from_bytes(content_bytes, filename)
            return self._format_response(filename, text, error)
        except Exception as e:
            return self._format_response(filename, "", f"Lỗi đọc file local: {str(e)}")

file_parser = FileParserService()