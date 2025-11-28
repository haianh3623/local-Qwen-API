from fastapi import APIRouter
from pydantic import BaseModel
from app.services.instruction_manager import instruction_manager

router = APIRouter()

class InstrUpdate(BaseModel):
    content: str

@router.get("/system-instruction")
def get_instr():
    return {"instruction": instruction_manager.get_instruction()}

@router.put("/system-instruction")
def update_instr(data: InstrUpdate):
    instruction_manager.update_instruction(data.content)
    return {"status": "success", "new_content": data.content}