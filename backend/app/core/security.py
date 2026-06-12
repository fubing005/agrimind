"""AgriMind 安全模块"""
from fastapi import HTTPException, status


class AgricultureGuardrailError(HTTPException):
    """非农业问题拦截异常"""

    definitive_answer: str = "我是农知睿策，我只能为您提供专业的农业相关知识解答。"

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_200_OK,
            detail={
                "blocked": True,
                "message": self.definitive_answer,
            },
        )
