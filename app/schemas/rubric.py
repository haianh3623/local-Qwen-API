from pydantic import BaseModel, Field
from typing import Dict, Any, Literal

class RubricFlattenRequest(BaseModel):
    # Loại công cụ chấm: "rubric" hoặc "marking_guide"
    type: Literal["rubric", "marking_guide"] = Field(..., description="Loại công cụ chấm")
    
    # Dữ liệu JSON thô lấy từ Moodle
    raw_data: Dict[str, Any] = Field(..., description="JSON cấu trúc rubric/guide từ Moodle")
    
    # Ngữ cảnh thêm (ví dụ tên bài tập)
    context: str = Field("", description="Tên bài tập hoặc ghi chú thêm")

class RubricFlattenResponse(BaseModel):
    natural_language_instruction: str = Field(..., description="Hướng dẫn chấm dạng văn bản tự nhiên")