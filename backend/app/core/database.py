"""数据库初始化与全局 Session 工厂"""
import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """统一的 SQLAlchemy 声明基类

    所有 ORM 模型都继承自本类，确保 ``Base.metadata.create_all`` 能一次
    性建出所有表。模型层**不要**自行调用 ``declarative_base()``。
    """


# 确保数据目录存在（SQLite 本地文件场景）
_data_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data")
os.makedirs(_data_dir, exist_ok=True)

# 数据库 URL：固定使用 backend/data/agrimind.db（与原项目一致）
SQLALCHEMY_DATABASE_URL = (
    f"sqlite:///{os.path.join(_data_dir, 'agrimind.db')}"
)

# SQLite 需要显式关闭跨线程检查
_connect_args = (
    {"check_same_thread": False}
    if SQLALCHEMY_DATABASE_URL.startswith("sqlite")
    else {}
)

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args=_connect_args)

# 会话工厂：禁用 autocommit / autoflush，由调用方显式控制事务
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """初始化数据库表（启动时调用）"""
    # 引入模型包以触发 ``Base`` 子类注册
    from app.models.session import Conversation  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖：每次请求提供一个 Session，请求结束自动关闭"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
