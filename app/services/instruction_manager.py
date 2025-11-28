import json
import os

class InstructionManager:
    def __init__(self):
        # Đường dẫn map với volume trong docker-compose
        self.file_path = "data/system_instruction.json"
        
        self.default_data = {
            "instruction": "Bạn là trợ giảng AI công tâm. Hãy chấm điểm dựa trên bằng chứng trong bài làm.",
            "version": 1,
            "last_updated": "init"
        }
        self._init_file()

    def _init_file(self):
        # Tạo thư mục data nếu chưa có (trong container)
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        if not os.path.exists(self.file_path):
            self._save(self.default_data)

    def _save(self, data):
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    def get_instruction(self) -> str:
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                return json.load(f).get("instruction", "")
        except:
            return self.default_data["instruction"]

    def update_instruction(self, content: str):
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except:
            data = self.default_data.copy()
            
        data["instruction"] = content
        data["version"] += 1
        self._save(data)

instruction_manager = InstructionManager()