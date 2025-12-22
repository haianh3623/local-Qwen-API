from pydantic import BaseModel, Field
from typing import List, Optional

class IngestRequest(BaseModel):
    file_path: str = Field(..., description="Đường dẫn file trên server (đã mount)")
    course_id: str = Field(..., description="Mã học phần để phân loại dữ liệu")

class IngestResponse(BaseModel):
    status: str
    chunks_processed: int
    message: str

class SearchRequest(BaseModel):
    query: str
    course_id: Optional[str] = None
    limit: int = 5

class SearchResult(BaseModel):
    content: str
    page: int
    source: str
    score: float