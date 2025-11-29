from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks
from typing import List, Optional, Union
import uuid

# Import đúng các module đã sửa
from app.services.llm_service import llm_service
from app.core.task_runner import task_runner
from app.core.common import process_upload_files, validate_submission_content 
# (Đảm bảo bạn đã có file app/core/common.py từ bước trước)

router = APIRouter()

@router.post("/async-batch", status_code=202)
async def grade_submission_async(
    # --- Meta ---
    callback_url: str = Form(..., description="Webhook URL nhận kết quả"),
    request_id: str = Form(None),
    
    # --- Inputs ---
    assignment_content: str = Form(...),
    assignment_attachments: Union[List[UploadFile], List[str], None] = File(None),
    
    student_submission_text: Optional[str] = Form(None),
    student_submission_files: Union[List[UploadFile], List[str], None] = File(None),
    
    reference_answer_text: Optional[str] = Form(None),
    reference_answer_file: Union[UploadFile, str, None] = File(None),
    
    grading_criteria: Optional[str] = Form(None),
    teacher_instruction: Optional[str] = Form(None),
    max_score: float = Form(10.0),
    
    # --- Background ---
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    # 1. Sinh ID nếu thiếu
    if not request_id:
        request_id = str(uuid.uuid4())

    # 2. Xử lý file (Dùng hàm chung trong common.py)
    q_files = await process_upload_files(assignment_attachments)
    s_files = await process_upload_files(student_submission_files)
    r_files = await process_upload_files(reference_answer_file)

    # 3. Validate
    validate_submission_content(student_submission_text, s_files)

    # 4. Gom dữ liệu
    grading_data = {
        "question": assignment_content + q_files,
        "submission": (student_submission_text or "") + s_files,
        "reference": (reference_answer_text or "") + r_files,
        "rubric": grading_criteria,
        "teacher_instruction": teacher_instruction,
        "max_score": max_score
    }

    # 5. Đẩy vào Background Task (Dùng Task Runner)
    background_tasks.add_task(
        task_runner.run_task_and_callback,      # Gọi hàm điều phối của Task Runner
        processing_function=llm_service.grade_submission, # Truyền hàm logic chấm điểm vào
        input_data=grading_data,                # Truyền dữ liệu vào
        callback_url=callback_url,
        request_id=request_id
    )

    return {
        "status": "queued",
        "message": "Đã tiếp nhận vào hàng đợi.",
        "request_id": request_id
    }