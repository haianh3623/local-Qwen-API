import os
import shutil
from typing import List, Generator
from langchain_community.document_loaders import PyMuPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from app.core.config import settings
import logging

logger = logging.getLogger("rag_service")
class RagService:
    def __init__(self):
        print("--- [RAG] Initializing Embedding Model & DB ---")
        # Load model vào RAM 1 lần duy nhất
        self.embedding_model = HuggingFaceEmbeddings(
            model_name=settings.RAG_EMBEDDING_MODEL,
            model_kwargs={'device': 'cpu'}, # Buộc chạy CPU để nhường GPU cho Ollama
            encode_kwargs={'normalize_embeddings': True}
        )
        
        self.vector_store = Chroma(
            collection_name="textbook_collection",
            embedding_function=self.embedding_model,
            persist_directory=settings.CHROMA_DB_DIR
        )

        self.text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            model_name="gpt-3.5-turbo",
            chunk_size=settings.RAG_CHUNK_SIZE,
            chunk_overlap=settings.RAG_CHUNK_OVERLAP
        )

    def _get_loader(self, file_path: str):
        logger.info(f"🗂️ [RAG] Getting loader for file: {file_path}")

        if file_path.endswith(".pdf"):
            return PyMuPDFLoader(file_path)
        elif file_path.endswith(".txt"):
            return TextLoader(file_path, encoding="utf-8")
        else:
            raise ValueError(f"Unsupported file type: {file_path}")

    def ingest_file(self, file_path: str, course_id: str) -> int:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        # 1. Lazy Load: PyMuPDFLoader hỗ trợ lazy_load() trả về iterator
        loader = self._get_loader(file_path)
        pages_iterator = loader.lazy_load() 

        chunks_buffer: List[Document] = []
        total_chunks = 0
        
        # 2. Stream Processing: Đọc trang -> Split -> Gom Batch -> Embed -> Xả RAM
        for page in pages_iterator:
            logger.info(f"🗂️ [RAG] Processing page {page.metadata.get('page', 'unknown')} of file {file_path}")
            # Split ngay từng trang
            page_chunks = self.text_splitter.split_documents([page])
            
            # Gán metadata
            for chunk in page_chunks:
                chunk.metadata["course_id"] = course_id
                chunk.metadata["source"] = file_path
                chunks_buffer.append(chunk)

            # Khi buffer đủ lớn (theo Config), đẩy vào DB và xóa buffer
            if len(chunks_buffer) >= settings.RAG_BATCH_SIZE:
                self.vector_store.add_documents(chunks_buffer)
                total_chunks += len(chunks_buffer)
                chunks_buffer.clear() # Giải phóng RAM ngay lập tức

        # Xử lý số dư còn lại trong buffer
        if chunks_buffer:
            self.vector_store.add_documents(chunks_buffer)
            total_chunks += len(chunks_buffer)
            chunks_buffer.clear()

        return total_chunks

    def search(self, query: str, course_id: str = None, limit: int = 5):
        filter_dict = {"course_id": course_id} if course_id else None
        
        results = self.vector_store.similarity_search_with_score(
            query, 
            k=limit, 
            filter=filter_dict
        )
        
        return [
            {
                "content": doc.page_content,
                "page": doc.metadata.get("page", 0),
                "source": doc.metadata.get("source", ""),
                "score": score
            } 
            for doc, score in results
        ]

    def reset_db(self):
        """Dùng cho testing hoặc reset dữ liệu"""
        self.vector_store.delete_collection()

# Singleton Instance
rag_service = RagService()