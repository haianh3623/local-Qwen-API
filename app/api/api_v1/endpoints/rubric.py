from fastapi import APIRouter, HTTPException
from app.schemas.rubric import RubricFlattenRequest, RubricFlattenResponse
from app.services.llm_service import llm_service

router = APIRouter()

@router.post("/flatten", response_model=RubricFlattenResponse)
async def flatten_rubric_data(request: RubricFlattenRequest):
    """
    API chuyển đổi cấu trúc Rubric/Marking Guide thô (JSON) -> Văn bản hướng dẫn tự nhiên.
    Moodle nên gọi API này khi GV lưu Rubric, sau đó lưu kết quả vào DB.
    """
    try:
        instruction = await llm_service.flatten_rubric(
            rubric_type=request.type,
            raw_data=request.raw_data,
            context=request.context
        )
        return RubricFlattenResponse(natural_language_instruction=instruction)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))