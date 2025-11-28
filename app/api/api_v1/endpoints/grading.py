from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import List, Optional, Union
from app.schemas.grading import GradingResponse
from app.services.llm_service import llm_service
from app.services.file_parser import file_parser

router = APIRouter()

@router.post("/comprehensive", response_model=GradingResponse)
async def grade_submission_comprehensive(
    # --- 1. ĐỀ BÀI ---
    assignment_content: str = Form(..., description="Nội dung đề bài"),
    
    # [FIX] Chấp nhận cả List lẫn Single File
    assignment_attachments: Union[List[UploadFile], UploadFile, None] = File(None),

    # --- 2. BÀI LÀM ---
    student_submission_text: Optional[str] = Form(None),
    
    # [FIX] Chấp nhận cả List lẫn Single File
    student_submission_files: Union[List[UploadFile], UploadFile, None] = File(None),

    # --- 3. THAM CHIẾU ---
    reference_answer_text: Optional[str] = Form(None),
    reference_answer_file: Optional[UploadFile] = File(None), # File đơn thì giữ nguyên
    
    grading_criteria: Optional[str] = Form(None),
    teacher_instruction: Optional[str] = Form(None),
    max_score: float = Form(10.0)
):
    
    # --- HÀM CHUẨN HÓA (Normalization) ---
    # Chuyển đổi mọi thứ thành List để dễ xử lý vòng lặp bên dưới
    def normalize_files(file_input: Union[List[UploadFile], UploadFile, None]) -> List[UploadFile]:
        if not file_input:
            return []
        if isinstance(file_input, list):
            return file_input
        return [file_input] # Nếu là file đơn, gói nó vào list

    # Chuẩn hóa input ngay đầu hàm
    attachments_list = normalize_files(assignment_attachments)
    submission_files_list = normalize_files(student_submission_files)

    # --- VALIDATION ---
    has_text = student_submission_text and student_submission_text.strip()
    has_file = len(submission_files_list) > 0
    
    if not has_text and not has_file:
        raise HTTPException(status_code=400, detail="Sinh viên chưa nộp bài (Thiếu cả text và file).")

    # --- GIAI ĐOẠN 1: PARSE DATA ---
    
    # 1. Tổng hợp Đề bài
    full_question = assignment_content
    for f in attachments_list:
        full_question += await file_parser.parse_file_to_text(f)

    # 2. Tổng hợp Bài làm
    full_submission = student_submission_text or ""
    for f in submission_files_list:
        full_submission += await file_parser.parse_file_to_text(f)

    # 3. Tổng hợp Đáp án mẫu
    full_reference = reference_answer_text or ""
    if reference_answer_file:
        full_reference += await file_parser.parse_file_to_text(reference_answer_file)

    # --- GIAI ĐOẠN 2: GỌI AI ---
    
    grading_data = {
        "question": full_question,
        "submission": full_submission,
        "reference": full_reference, 
        "rubric": grading_criteria,
        "teacher_instruction": teacher_instruction,
        "max_score": max_score
    }

    try:
        return await llm_service.grade_comprehensive(grading_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý: {str(e)}")