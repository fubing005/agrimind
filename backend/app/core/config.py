
"""AgriMind 核心配置模块"""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """应用全局配置，从 .env 文件读取"""

    # 项目基础信息
    PROJECT_NAME: str = "农知睿策 AgriMind"
    VERSION: str = "0.1.0"
    API_V1_PREFIX: str = "/api/v1"

    # CORS 允许的来源
    ALLOWED_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # OpenAI 配置
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4o-mini"

    # Tavily 联网搜索配置
    TAVILY_API_KEY: str = ""

    # 数据库配置
    DATABASE_URL: str = "sqlite:///./agrimind.db"

    # LlamaIndex / ChromaDB 配置
    CHROMA_PERSIST_DIR: str = "./chroma_db"
    CHROMA_COLLECTION_NAME: str = "agri_knowledge"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 50

    # 边界拦截器配置
    GUARDRAIL_MAX_RETRIES: int = 1
    GUARDRAIL_TEMPERATURE: float = 0.0

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


settings = Settings()
