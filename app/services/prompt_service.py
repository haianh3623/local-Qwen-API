import os
from datetime import datetime
from app.services.instruction_manager import instruction_manager
from app.services.rag_service import rag_service
import json
import re
import logging

logger = logging.getLogger("prompt_service")
class PromptService:
    def _log_prompt_to_file(self, prompt_content: str, filename: str):
        """
        Ghi log prompt ra file để debug.
        """
        try:
            log_dir = "app/logs"
            os.makedirs(log_dir, exist_ok=True)
            file_path = os.path.join(log_dir, filename)
            with open(file_path, "w", encoding="utf-8") as f:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"=== DEBUG PROMPT LOG - {timestamp} ===\n\n")
                f.write(prompt_content)
                f.write("\n\n==========================================\n")
        except Exception as e:
            print(f"Error logging prompt: {e}")

    def _split_questions(self, raw_text: str) -> list:
        """
        Tách nhiều câu hỏi từ văn bản thô.
        Giả sử các câu hỏi được đánh số theo định dạng "1.", "2.", ...
        Trả về danh sách các câu hỏi.
        """
        pattern = r"((?:^|\n)\s*(?:Câu|Bài|Phần)?\s*\d+[:.)])"  # Tìm định dạng số câu hỏi
        splits = re.split(pattern, raw_text)
        questions = [s.strip() for s in splits if s.strip()]
        return questions

    def build_grading_prompt(self, course_id, question, submission, max_score, reference=None, rubric=None, teacher_instruction=None):
        
        # 1. System Instruction
        sys_instr = instruction_manager.get_instruction()

        # 2. Teacher Instruction
        teacher_block = ""
        if teacher_instruction:
            teacher_block = f"{teacher_instruction}"
        else:
            teacher_block = "Không có yêu cầu bổ sung."

        # 3. Context (Rubric/Reference)
        grading_criteria_content = ""
        if rubric:
            grading_criteria_content = f"TUÂN THỦ RUBRIC SAU:\n{rubric}"
        elif reference:
            grading_criteria_content = f"SO SÁNH VỚI ĐÁP ÁN MẪU:\n{reference}"
        else:
            grading_criteria_content = "Đánh giá dựa trên kiến thức chuyên gia của bạn về vấn đề này."

        textbook_refs = ""
        questions = self._split_questions(question)
        if len(questions) < 1: questions = [question]
        logger.info(f"Split into {len(questions)} questions for RAG.")
        for q in questions:   
            logger.info(f"Processing RAG for question: {q[:50]}...")
            if not course_id:
                break
            raw_results = rag_service.search(q, course_id=course_id, limit=3)
            logger.info(f"RAG returned {len(raw_results)} results.")
            textbook_refs += json.dumps(raw_results, ensure_ascii=False, indent=2)

        # 4. Final Prompt với cấu trúc thẻ XML
        prompt = f"""
<system_role>
{sys_instr}
</system_role>

<teacher_instruction>
{teacher_block}
</teacher_instruction>

<problem_statement>
{question}
</problem_statement>

<grading_criteria>
{grading_criteria_content}
</grading_criteria>

<student_submission>
{submission}
</student_submission>

<output_requirements>
1. Nhiệm vụ: Chấm điểm và nhận xét bài làm trong thẻ <student_submission> dựa trên <problem_statement> và <grading_criteria>.
2. Thang điểm: 0 đến {max_score}.
3. Định dạng Output: Trả về DUY NHẤT một JSON object hợp lệ.
4. Cấu trúc JSON bắt buộc:
{{
    "score": <số thực>,
    "feedback": "<nhận xét chi tiết bằng tiếng Việt>"
}}
</output_requirements>

<textbook_references>
Sử dụng tài liệu tham khảo sau để hỗ trợ chấm điểm (nếu cần):
{textbook_refs}
</textbook_references>
"""
        
        # Ghi log để kiểm tra
        self._log_prompt_to_file(prompt.strip(), "latest_grading_prompt.txt")
        
        return prompt.strip()

    def build_rubric_flattening_prompt(self, rubric_type: str, raw_data: dict, context: str) -> str:
        """
        Tạo prompt làm phẳng Rubric với cấu trúc thẻ.
        """
        data_str = str(raw_data)
        
        # Chiến lược xử lý
        strategy_instruction = ""
        if rubric_type == "rubric":
            strategy_instruction = (
                "Dữ liệu là RUBRIC (Ma trận). Hãy mô tả sự phân cấp giữa các mức điểm (Xuất sắc vs Khá vs Yếu). "
                "Dùng từ ngữ so sánh để làm rõ sự khác biệt."
            )
        elif rubric_type == "marking_guide":
            strategy_instruction = (
                "Dữ liệu là MARKING GUIDE (Hướng dẫn chấm). Hãy trích xuất thành danh sách các ý chính (Checklist) cần có. "
                "Nêu rõ nếu thiếu ý nào thì trừ điểm ra sao."
            )
        else:
            strategy_instruction = "Tóm tắt tiêu chí chấm điểm rõ ràng, dễ hiểu."

        # Prompt làm phẳng
        prompt = f"""
<role>
Bạn là chuyên gia sư phạm. Nhiệm vụ là chuyển đổi dữ liệu chấm điểm thô (JSON) thành văn bản hướng dẫn chấm thi (Natural Language).
</role>

<context>
Loại công cụ: {rubric_type.upper()}
Bối cảnh: {context if context else "N/A"}
</context>

<task_instruction>
{strategy_instruction}
Yêu cầu văn phong: Tự nhiên, mạch lạc, chuyên nghiệp (như Trưởng bộ môn dặn dò).
Định dạng: Văn bản thuần (Plain text), tiếng Việt.
</task_instruction>

<raw_data>
{data_str}
</raw_data>

<output_directive>
Hãy viết bản hướng dẫn chi tiết dựa trên <raw_data> ở trên. Bắt đầu ngay:
</output_directive>
"""
        
        # self._log_prompt_to_file(prompt.strip(), "latest_rubric_prompt.txt")
        
        return prompt.strip()

prompt_service = PromptService()