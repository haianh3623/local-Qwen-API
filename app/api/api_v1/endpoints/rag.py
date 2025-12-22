from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List
from app.schemas.rag import IngestRequest, IngestResponse, SearchRequest, SearchResult
from app.services.rag_service import rag_service

router = APIRouter()

@router.post("/ingest", response_model=IngestResponse)
async def ingest_textbook(request: IngestRequest, background_tasks: BackgroundTasks):
    """
    Xử lý file giáo trình (chạy ngầm).
    """
    import os
    if not os.path.exists(request.file_path):
        raise HTTPException(status_code=400, detail="File path does not exist on server")

    # Đẩy task vào background để trả response ngay
    background_tasks.add_task(
        rag_service.ingest_file, 
        request.file_path, 
        request.course_id
    )

    return IngestResponse(
        status="processing",
        chunks_processed=0,
        message=f"Started processing {os.path.basename(request.file_path)} in background"
    )

@router.post("/search", response_model=List[SearchResult])
async def search_knowledge_base(request: SearchRequest):
    """
    Tìm kiếm thông tin trong giáo trình.
    """
    try:
        results = rag_service.search(
            query=request.query,
            course_id=request.course_id,
            limit=request.limit
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))