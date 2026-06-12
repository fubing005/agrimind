"""本地知识库 RAG 检索模块 — 基于 LlamaIndex + ChromaDB"""
import logging
from typing import Optional

from llama_index.core import VectorStoreIndex, StorageContext, load_index_from_storage
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import Document
from llama_index.llms.openai import OpenAI as LlamaOpenAI
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore

import chromadb

from app.core.config import settings

logger = logging.getLogger(__name__)

# 全局索引实例（懒加载）
_index: Optional[VectorStoreIndex] = None


def _get_embed_model() -> OpenAIEmbedding:
    """获取 OpenAI Embedding 模型实例"""
    return OpenAIEmbedding(
        api_key=settings.OPENAI_API_KEY,
        api_base=settings.OPENAI_BASE_URL,
        model=settings.EMBEDDING_MODEL,
    )


def _get_llm() -> LlamaOpenAI:
    """获取 LlamaIndex 使用的 OpenAI LLM 实例"""
    return LlamaOpenAI(
        api_key=settings.OPENAI_API_KEY,
        api_base=settings.OPENAI_BASE_URL,
        model=settings.OPENAI_MODEL,
        temperature=0.1,
    )


def _get_chroma_store() -> ChromaVectorStore:
    """获取 ChromaDB 向量存储实例"""
    chroma_client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
    chroma_collection = chroma_client.get_or_create_collection(
        name=settings.CHROMA_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    return ChromaVectorStore(chroma_collection=chroma_collection)


def get_index() -> VectorStoreIndex:
    """获取或创建向量索引（单例模式）

    优先从持久化存储加载已有索引，若不存在则创建空索引。

    Returns:
        VectorStoreIndex 实例
    """
    global _index
    if _index is not None:
        return _index

    embed_model = _get_embed_model()
    vector_store = _get_chroma_store()

    try:
        # 尝试从 ChromaDB 持久化存储加载
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        _index = VectorStoreIndex.from_vector_store(
            vector_store=vector_store,
            embed_model=embed_model,
        )
        doc_count = vector_store._collection.count()
        logger.info(f"从 ChromaDB 加载索引成功，当前文档数: {doc_count}")
    except Exception as e:
        logger.warning(f"加载索引失败，创建空索引: {e}")
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        _index = VectorStoreIndex(
            [],
            storage_context=storage_context,
            embed_model=embed_model,
        )

    return _index


def add_documents(documents: list[Document]) -> int:
    """向知识库添加文档

    将文档分块、向量化并存入 ChromaDB。

    Args:
        documents: LlamaIndex Document 列表

    Returns:
        生成的分块数量
    """
    index = get_index()

    # # 文档分块
    # splitter = SentenceSplitter(
    #     chunk_size=settings.CHUNK_SIZE,
    #     chunk_overlap=settings.CHUNK_OVERLAP,
    # )
    # nodes = splitter.get_nodes_from_documents(documents)

    # # 插入索引
    # for node in nodes:
    #     index.insert(node)

    # logger.info(f"成功添加 {len(documents)} 个文档，生成 {len(nodes)} 个分块")
    # return len(nodes)

    # 插入文档（VectorStoreIndex 内部会自动进行分块处理）
    for doc in documents:
        index.insert(doc)

    logger.info(f"成功添加 {len(documents)} 个文档")
    return len(documents)


async def local_rag_search(query: str, top_k: int = 5, similarity_threshold: float = 0.6) -> tuple[str, list[str]]:
    """本地知识库语义检索

    Args:
        query: 查询文本
        top_k: 返回最相关的 K 个结果
        similarity_threshold: 相似度阈值，低于此值的结果将被过滤

    Returns:
        (检索结果文本, 引用来源列表)
    """
    try:
        index = get_index()
        retriever = index.as_retriever(similarity_top_k=top_k)

        # 执行检索
        nodes = retriever.retrieve(query)

        if not nodes:
            logger.info(f"本地 RAG 未检索到相关结果: '{query[:50]}...'")
            return "", []

        # 过滤低相似度结果并拼接上下文
        context_parts = []
        sources = []
        for node in nodes:
            score = node.score if node.score is not None else 0.0
            if score >= similarity_threshold:
                context_parts.append(node.node.get_content())
                # 提取来源信息
                metadata = node.node.metadata
                source_name = metadata.get("filename", metadata.get("source", "本地知识库"))
                if source_name not in sources:
                    sources.append(source_name)

        context = "---".join(context_parts)
        logger.info(
            f"本地 RAG 检索完成: 查询='{query[:30]}...', "
            f"命中={len(context_parts)}/{len(nodes)}, 来源={sources}"
        )

        return context, sources

    except Exception as e:
        logger.error(f"本地 RAG 检索异常: {e}")
        return "", []


def get_knowledge_base_info() -> dict:
    """获取知识库统计信息

    Returns:
        包含 document_count 和 chunk_count 的字典
    """
    try:
        vector_store = _get_chroma_store()
        count = vector_store._collection.count()
        return {
            "document_count": count,  # 近似值，ChromaDB 按 chunk 计数
            "chunk_count": count,
        }
    except Exception as e:
        logger.error(f"获取知识库信息异常: {e}")
        return {"document_count": 0, "chunk_count": 0}
