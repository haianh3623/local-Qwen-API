from pydantic import BaseModel, Field
from typing import Optional

class GradingResponse(BaseModel):
    score: Optional[float] = Field(None, description="Điểm số (Null nếu lỗi)")
    feedback: Optional[str] = Field(None, description="Nhận xét (Null nếu lỗi)")
    error: Optional[str] = Field(None, description="Thông báo lỗi nếu có")  
    ai_model: str