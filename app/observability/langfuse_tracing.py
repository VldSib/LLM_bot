"""Langfuse: CallbackHandler для LangGraph + flush. Один запрос пользователя — один handler."""
from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Any, Generator, List

from app.config import settings

_init_lock = threading.Lock()
_client_ready = False


def _langfuse_configured() -> bool:
    return bool(
        settings.langfuse_enabled
        and settings.langfuse_public_key.strip()
        and settings.langfuse_secret_key.strip()
    )


def _ensure_langfuse_client() -> None:
    """Langfuse SDK 3.x: регистрирует клиент по public_key до get_client / CallbackHandler / propagate_attributes."""
    global _client_ready
    if not _langfuse_configured():
        return
    if _client_ready:
        return
    with _init_lock:
        if _client_ready:
            return
        try:
            from langfuse import Langfuse
        except ImportError:
            return
        Langfuse(
            public_key=settings.langfuse_public_key.strip(),
            secret_key=settings.langfuse_secret_key.strip(),
            host=settings.langfuse_host.rstrip("/"),
        )
        _client_ready = True


def langfuse_callbacks_for_chat(chat_id: int) -> List[Any]:
    """
    Возвращает список callback handlers для graph.invoke(..., config={"callbacks": ...}).
    Пустой список, если Langfuse выключен или не настроен.
    """
    if not _langfuse_configured():
        return []
    _ensure_langfuse_client()
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
    _ensure_langfuse_client()
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
    _ensure_langfuse_client()
    try:
        from langfuse import get_client
    except ImportError:
        return
    try:
        get_client(public_key=settings.langfuse_public_key.strip()).flush()
    except Exception as e:
        print(f"[langfuse] flush: {e}")
