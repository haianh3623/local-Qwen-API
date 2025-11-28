import json
import os

class InstructionManager:
    def __init__(self):
        # Đường dẫn file lưu cấu hình (nằm trong volume để không mất khi restart)
        self.file_path = "data/system_instruction.json"
        self.default_instruction = (
            "Bạn là một trợ giảng AI chuyên nghiệp, công tâm và nghiêm túc. "
            "Hãy chấm điểm dựa trên bằng chứng thực tế trong bài làm, không thiên vị. "
            "Luôn đưa ra nhận xét mang tính xây dựng để giúp sinh viên tiến bộ."
        )
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        # Tạo thư mục data nếu chưa có
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        
        # Nếu file chưa tồn tại, tạo mới với nội dung mặc định
        if not os.path.exists(self.file_path):
            self.update_instruction(self.default_instruction)

    def get_instruction(self) -> str:
        """Đọc hướng dẫn hiện tại từ file"""
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("instruction", self.default_instruction)
        except Exception:
            return self.default_instruction

    def update_instruction(self, new_text: str):
        """Cập nhật hướng dẫn mới"""
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump({"instruction": new_text}, f, ensure_ascii=False, indent=4)

instruction_manager = InstructionManager()