from __future__ import annotations

import hashlib
import re
from typing import Any

# Patterns for basic PII redaction in trace metadata.
# Note: мы санитизируем строки только перед отправкой "ручных" payload'ов
# (metadata/атрибуты). Input/output самих сообщений модели сейчас не
# перехватывается этим слоем без рефакторинга.

EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_PATTERN = re.compile(r"(?:(?:\+?\d{1,3}[\s-]?)?(?:\(?\d{2,3}\)?[\s-]?)?\d{3}[\s-]?\d{2}[\s-]?\d{2}))")

# Common token-like strings (best-effort).
SK_PREFIX_PATTERN = re.compile(r"\b(sk-[A-Za-z0-9_-]+)\b")
PK_PREFIX_PATTERN = re.compile(r"\b(pk-[A-Za-z0-9_-]+)\b")


def hash_user_id(user_id: str) -> str:
    """
    Стабильный хэш идентификатора пользователя.
    Возвращает вид: u_<16hex>.
    """
    h = hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:16]
    return f"u_{h}"


def sanitize_text(text: str) -> str:
    """Маскирует базовые PII/секреты в строке."""
    s = text
    s = EMAIL_PATTERN.sub("<email>", s)
    s = PHONE_PATTERN.sub("<phone>", s)
    s = SK_PREFIX_PATTERN.sub("<secret_key>", s)
    s = PK_PREFIX_PATTERN.sub("<public_key>", s)
    return s


def sanitize_payload(payload: Any) -> Any:
    """
    Рекурсивная санитизация payload:
    - str: sanitize_text
    - dict/list: рекурсивно по значениям
    - прочее: без изменений
    """
    if payload is None:
        return None
    if isinstance(payload, str):
        return sanitize_text(payload)
    if isinstance(payload, dict):
        return {str(k): sanitize_payload(v) for k, v in payload.items()}
    if isinstance(payload, list):
        return [sanitize_payload(v) for v in payload]
    if isinstance(payload, tuple):
        return [sanitize_payload(v) for v in payload]
    return payload

