from pydantic import BaseModel, Field
from typing import Optional

class GradingResponse(BaseModel):
    score: Optional[float] = Field(None, description="Điểm số (Null nếu lỗi)")
    feedback: Optional[str] = Field(None, description="Nhận xét (Null nếu lỗi)")
    error: Optional[str] = Field(None, description="Thông báo lỗi nếu có")  
    ai_model: str

class WebhookPayload(BaseModel):
    request_id: str = Field(..., description="ID để client map với request gốc")
    status: str = Field(..., description="success | error")
    timestamp: str = Field(..., description="Thời gian hoàn thành")
    data: Optional[GradingResponse] = Field(None, description="Kết quả chi tiết")
    system_error: Optional[str] = Field(None, description="Lỗi hệ thống (nếu có)")