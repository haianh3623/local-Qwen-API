import io
import logging
import re
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
        # Tách thành các đoạn văn (dựa trên 2 dấu xuống dòng trở lên)
        paragraphs = re.split(r'\n\s*\n', text)
        
        cleaned_paragraphs = []
        for p in paragraphs:
            # Trong mỗi đoạn, thay thế dấu xuống dòng đơn lẻ bằng dấu cách
            clean_p = re.sub(r'\n+', ' ', p).strip()
            # Xóa khoảng trắng kép
            clean_p = re.sub(r'\s+', ' ', clean_p)
            if clean_p:
                cleaned_paragraphs.append(clean_p)
        
        # Ghép lại các đoạn văn bằng dấu xuống dòng chuẩn
        return "\n\n".join(cleaned_paragraphs)

    async def parse_file_to_text(self, file: UploadFile) -> str:
        """
        Đọc file và trả về nội dung được bọc trong thẻ XML.
        Output format:
        <file_attachment name="filename.ext">
        ... content ...
        </file_attachment>
        """
        if not file:
            return ""
        
        original_filename = file.filename
        # Chuẩn hóa tên file để tránh lỗi nếu tên file chứa ký tự lạ
        safe_filename = original_filename.replace('"', '').replace('<', '').replace('>', '')
        
        filename = original_filename.lower()
        content_bytes = await file.read()
        file_text = ""
        error_msg = None

        try:
            # --- CASE 1: FILE TEXT ---
            if filename.endswith((".txt", ".md", ".json", ".py", ".php", ".html", ".css", ".js", ".java", ".cpp")):
                file_text = content_bytes.decode("utf-8", errors="ignore")

            # --- CASE 2: FILE PDF ---
            elif filename.endswith(".pdf"):
                try:
                    pdf_reader = PdfReader(io.BytesIO(content_bytes))
                    for page in pdf_reader.pages:
                        # Ưu tiên chế độ layout để giữ bố cục
                        try:
                            text = page.extract_text(extraction_mode="layout")
                        except:
                            text = page.extract_text()
                        if text:
                            file_text += text + "\n"
                    
                    if not file_text.strip():
                        error_msg = "File PDF này không chứa văn bản (có thể là file scan/ảnh)."

                except Exception as pdf_err:
                    error_msg = f"Lỗi đọc PDF: {str(pdf_err)}"

            # --- CASE 3: FILE WORD ---
            elif filename.endswith(".docx"):
                try:
                    doc = Document(io.BytesIO(content_bytes))
                    for para in doc.paragraphs:
                        file_text += para.text + "\n"
                except Exception as docx_err:
                    error_msg = f"Lỗi đọc DOCX: {str(docx_err)}"
            
            # --- CASE 4: KHÔNG HỖ TRỢ ---
            else:
                error_msg = f"Định dạng file không được hỗ trợ."

            # Reset con trỏ file
            await file.seek(0)
            
            # Xử lý kết quả trả về
            if error_msg:
                # Trả về thẻ lỗi để AI biết file này có vấn đề
                return f"""
<file_attachment name="{safe_filename}">
[SYSTEM ERROR: {error_msg}]
</file_attachment>
"""

            # Làm sạch văn bản
            cleaned_text = self._clean_text(file_text)
            
            # Trả về nội dung bọc trong thẻ
            return f"""
<file_attachment name="{safe_filename}">
{cleaned_text}
</file_attachment>
"""

        except Exception as e:
            logger.error(f"Critical error parsing {original_filename}: {e}")
            return f"""
<file_attachment name="{safe_filename}">
[SYSTEM CRITICAL ERROR: {str(e)}]
</file_attachment>
"""

file_parser = FileParserService()