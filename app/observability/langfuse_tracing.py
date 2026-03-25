"""Langfuse: CallbackHandler для LangGraph + flush. Один запрос пользователя — один handler."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Generator, List, Optional

from app.config import settings


def _langfuse_configured() -> bool:
    return bool(
        settings.langfuse_enabled
        and settings.langfuse_public_key.strip()
        and settings.langfuse_secret_key.strip()
    )


def langfuse_callbacks_for_chat(chat_id: int) -> List[Any]:
    """
    Возвращает список callback handlers для graph.invoke(..., config={"callbacks": ...}).
    Пустой список, если Langfuse выключен или не настроен.
    """
    if not _langfuse_configured():
        return []
    try:
        from langfuse.langchain import CallbackHandler
    except ImportError:
        print("[langfuse] Пакет langfuse не установлен. Установите: pip install 'langfuse>=3,<4'")
        return []

    handler = CallbackHandler(public_key=settings.langfuse_public_key.strip())
    return [handler]


@contextmanager
def langfuse_chat_context(chat_id: int) -> Generator[None, None, None]:
    """
    Оборачивает вызов графа: session_id / user_id для группировки трейсов по Telegram chat_id.
    """
    if not _langfuse_configured():
        yield
        return
    try:
        from langfuse import propagate_attributes
    except ImportError:
        yield
        return

    sid = str(chat_id)
    with propagate_attributes(
        session_id=sid,
        user_id=sid,
        metadata={"telegram_chat_id": sid, "app": "llm_bot"},
    ):
        yield


def flush_langfuse() -> None:
    """Сбрасывает буфер событий Langfuse (важно после запроса в долгоживущем процессе)."""
    if not _langfuse_configured():
        return
    try:
        from langfuse import get_client
    except ImportError:
        return
    try:
        get_client(public_key=settings.langfuse_public_key.strip()).flush()
    except Exception as e:
        print(f"[langfuse] flush: {e}")
