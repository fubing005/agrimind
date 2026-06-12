"""知识库相关的 Pydantic 数据校验模型"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class KnowledgeBaseInfo(BaseModel):
    """知识库信息"""
    name: str = Field(description="知识库名称")
    document_count: int = Field(description="文档数量")
    chunk_count: int = Field(description="分块数量")
    last_updated: Optional[datetime] = Field(default=None, description="最后更新时间")


class KnowledgeUploadRequest(BaseModel):
    """知识库文档上传请求"""
    filename: str = Field(description="文件名")
    description: Optional[str] = Field(default=None, description="文档描述")


class KnowledgeUploadResponse(BaseModel):
    """知识库文档上传响应"""
    success: bool = Field(description="是否上传成功")
    document_id: Optional[str] = Field(default=None, description="文档ID")
    chunk_count: Optional[int] = Field(default=None, description="生成的分块数量")
    message: str = Field(description="响应消息")
