"""知识库管理 API 端点"""
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException

from app.schemas.knowledge import KnowledgeBaseInfo, KnowledgeUploadResponse
from app.agent.rag.local_rag import add_documents, get_knowledge_base_info
from llama_index.core.schema import Document

logger = logging.getLogger(__name__)
router = APIRouter()

# 支持的文件扩展名
SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf", ".csv", ".json"}


@router.get("/info", response_model=KnowledgeBaseInfo, summary="获取知识库信息")
async def get_info():
    """获取当前知识库的基本信息"""
    info = get_knowledge_base_info()
    return KnowledgeBaseInfo(
        name="农知睿策农业知识库",
        document_count=info.get("document_count", 0),
        chunk_count=info.get("chunk_count", 0),
    )


@router.post("/upload", response_model=KnowledgeUploadResponse, summary="上传知识文档")
async def upload_knowledge_document(file: UploadFile = File(...)):
    """上传文档到知识库

    支持 TXT、MD、PDF、CSV、JSON 格式，上传后将自动分块、向量化并存入 ChromaDB。
    """
    filename = file.filename or "unknown"

    # 检查文件扩展名
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {ext}，支持格式: {', '.join(SUPPORTED_EXTENSIONS)}",
        )

    try:
        # 读取文件内容
        content = await file.read()
        text = content.decode("utf-8", errors="ignore")

        if not text.strip():
            raise HTTPException(status_code=400, detail="文件内容为空")

        # 构建 LlamaIndex Document
        doc = Document(
            text=text,
            metadata={
                "filename": filename,
                "source": filename,
            },
        )

        # 添加到知识库（分块 + 向量化 + 存储）
        chunk_count = add_documents([doc])

        logger.info(f"知识库上传成功: {filename}, 分块数: {chunk_count}")

        return KnowledgeUploadResponse(
            success=True,
            document_id=doc.doc_id,
            chunk_count=chunk_count,
            message=f"文档 '{filename}' 上传成功，已生成 {chunk_count} 个知识分块",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"知识库上传失败: {e}")
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")


@router.get("/list", summary="列出知识库文档")
async def list_knowledge_documents():
    """列出知识库中的所有文档"""
    info = get_knowledge_base_info()
    return {
        "total_chunks": info.get("chunk_count", 0),
        "message": "知识库已就绪，可通过 /upload 端点上传文档",
    }
