"""LangGraph Checkpointer 工厂

根据 ``settings.CHECKPOINTER_BACKEND`` 返回不同的 checkpointer：

- ``memory``  → :class:`langgraph.checkpoint.memory.MemorySaver`，进程内存，
  仅供演示与单元测试，进程重启即丢失。
- ``sqlite``  → :class:`langgraph.checkpoint.sqlite.aio.AsyncSqliteSaver`，
  写入 SQLite 文件。该文件与 session 业务库共用同一个 ``agrimind.db``；
  checkpointer 自身会在该库中创建 ``checkpoints`` / ``checkpoint_blobs`` /
  ``checkpoint_writes`` 表，与业务表 ``conversations`` 互不干扰。

模块级单例：FastAPI 整个进程共享同一个 checkpointer。
AsyncSqliteSaver 使用 aiosqlite 异步连接，天然兼容 async 图执行。
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Optional

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from app.core.config import settings

from typing import AsyncContextManager, Optional

logger = logging.getLogger(__name__)

_checkpointer: Optional[BaseCheckpointSaver] = None
_sqlite_ctx: Optional[AsyncContextManager] = None  # 保存上下文管理器，进程退出时可清理
_lock = threading.Lock()


def _resolve_sqlite_path() -> str:
    """复用与 session 业务库相同的 SQLite 文件路径（转为绝对路径）。

    优先解析 ``settings.DATABASE_URL`` 中的 ``sqlite:///<path>``；若解析
    失败，则回退到 ``backend/data/agrimind.db``。

    返回的始终是绝对路径，避免 ``from_conn_string`` 因工作目录不同而
    出现 ``unable to open database file`` 错误。
    """
    url = (settings.DATABASE_URL or "").strip()
    raw_path = ""
    if url.startswith("sqlite:///"):
        raw_path = url[len("sqlite:///") :]

    if not raw_path:
        fallback_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data")
        raw_path = os.path.normpath(os.path.join(fallback_dir, "agrimind.db"))

    # 确保父目录存在
    abs_path = os.path.abspath(raw_path)
    parent = os.path.dirname(abs_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    logger.info("Checkpointer SQLite 路径: %s", abs_path)
    return abs_path


async def _build_async_sqlite_saver() -> BaseCheckpointSaver:
    """构建 AsyncSqliteSaver 实例（异步连接池，兼容 ainvoke）。

    ``from_conn_string`` 返回异步上下文管理器，必须 ``await __aenter__()``
    才能拿到真正的 saver 实例。上下文管理器保存在模块级变量中，
    进程退出时由 :func:`cleanup_checkpointer` 负责关闭。
    """
    global _sqlite_ctx
    db_path = _resolve_sqlite_path()
    ctx = AsyncSqliteSaver.from_conn_string(db_path)
    # 进入上下文管理器，获取真正的 AsyncSqliteSaver 实例
    saver = await ctx.__aenter__()
    _sqlite_ctx = ctx
    # 显式建表，幂等
    await saver.setup()

    logger.info("Checkpointer 使用 AsyncSqliteSaver: %s", db_path)
    return saver


async def cleanup_checkpointer() -> None:
    """关闭 AsyncSqliteSaver 的异步连接。

    应在 FastAPI shutdown 事件中调用。
    """
    global _checkpointer, _sqlite_ctx
    if _sqlite_ctx is not None:
        try:
            await _sqlite_ctx.__aexit__(None, None, None)
        except Exception:  # noqa: BLE001
            pass
        _sqlite_ctx = None
        _checkpointer = None


def _build_checkpointer() -> BaseCheckpointSaver:
    """根据配置构建 checkpointer 实例。

    - memory: 同步返回 MemorySaver
    - sqlite: 返回一个占位 MemorySaver，真正的 AsyncSqliteSaver 由
      :func:`ensure_checkpointer` 在首次异步调用时懒初始化
    """
    backend = (settings.CHECKPOINTER_BACKEND or "memory").strip().lower()

    if backend == "memory":
        logger.info("Checkpointer 使用 MemorySaver（演示模式，重启会丢失记忆）")
        return MemorySaver()

    if backend == "sqlite":
        # AsyncSqliteSaver 需要异步初始化，此处先返回 MemorySaver 占位
        # 由 ensure_checkpointer() 在异步上下文中替换为真正的实例
        logger.info("Checkpointer 将使用 AsyncSqliteSaver（需异步初始化）")
        return MemorySaver()

    raise ValueError(
        f"未知的 CHECKPOINTER_BACKEND={backend!r}，仅支持 'memory' / 'sqlite'"
    )


def get_checkpointer() -> BaseCheckpointSaver:
    """返回进程级单例 checkpointer（线程安全双检锁）。

    注意：当 BACKEND=sqlite 时，此方法返回的是占位 MemorySaver；
    真正的 AsyncSqliteSaver 需通过 :func:`ensure_checkpointer` 异步初始化。
    """
    global _checkpointer
    if _checkpointer is not None:
        return _checkpointer
    with _lock:
        if _checkpointer is None:
            _checkpointer = _build_checkpointer()
    return _checkpointer


async def ensure_checkpointer() -> BaseCheckpointSaver:
    """确保 checkpointer 已完成异步初始化，返回可用的实例。

    应用启动时应调用此函数，以便在 sqlite 模式下完成
    AsyncSqliteSaver 的异步连接与建表。
    """
    global _checkpointer
    backend = (settings.CHECKPOINTER_BACKEND or "memory").strip().lower()

    if backend == "sqlite":
        with _lock:
            if _checkpointer is None or isinstance(_checkpointer, MemorySaver):
                _checkpointer = await _build_async_sqlite_saver()

    if _checkpointer is None:
        with _lock:
            if _checkpointer is None:
                _checkpointer = _build_checkpointer()

    return _checkpointer
