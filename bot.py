"""
Telegram-бот с локальной LLM (Ollama).
Лёгкие зависимости, работает без облачных API.
"""
import os
import logging

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from ollama import AsyncClient

load_dotenv()
# На Windows файл мог сохраниться как .env.txt
if not os.getenv("TELEGRAM_BOT_TOKEN"):
    load_dotenv(".env.txt")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Убрать лишний вывод запросов к Telegram API
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

# Модель Ollama (должна быть скачана: ollama pull <model>)
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:1b")

# История чата: chat_id -> список последних сообщений {"role": "user"|"assistant", "content": str}
CHAT_HISTORY: dict[int, list[dict[str, str]]] = {}
# Сколько предыдущих сообщений подставлять в контекст (пар: пользователь + бот)
HISTORY_LENGTH = 5


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Привет! Я бот с локальной LLM (Ollama). Напиши что-нибудь — я отвечу."
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Команды:\n"
        "/start — приветствие\n"
        "/help — эта справка\n"
        "Любое сообщение — отправляется в LLM, ответ придёт сюда.\n\n"
        "Убедись, что Ollama запущена и модель скачана:\n"
        f"  ollama run {OLLAMA_MODEL}"
    )


def _get_history_messages(chat_id: int) -> list[dict[str, str]]:
    """Последние HISTORY_LENGTH пар сообщений (user + assistant) для контекста."""
    history = CHAT_HISTORY.get(chat_id, [])
    # Берём последние HISTORY_LENGTH * 2 сообщений (пары)
    n = HISTORY_LENGTH * 2
    return history[-n:] if len(history) > n else history


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_text = (update.message.text or "").strip()
    if not user_text:
        await update.message.reply_text("Напиши текст сообщения.")
        return

    chat_id = update.effective_chat.id
    # Собираем контекст: предыдущие сообщения + текущее
    messages = _get_history_messages(chat_id) + [{"role": "user", "content": user_text}]

    reply_ok = False
    try:
        client = AsyncClient()
        response = await client.chat(
            model=OLLAMA_MODEL,
            messages=messages,
        )
        # Поддержка и объекта, и словаря (разные версии ollama)
        msg = getattr(response, "message", None)
        if msg is None and isinstance(response, dict):
            msg = response.get("message", {})
        content = getattr(msg, "content", None) if hasattr(msg, "content") else (msg.get("content", "") if isinstance(msg, dict) else "")
        reply = (content or "").strip() or "(пустой ответ)"
        reply_ok = True
    except Exception as e:
        err = str(e)
        if "Ollama" in err or "connect" in err.lower():
            reply = (
                "Не удаётся подключиться к Ollama. Убедись, что:\n"
                "1) Ollama установлена (ollama.com)\n"
                "2) Ollama запущена (в трее или: ollama serve)\n"
                "3) Модель скачана: ollama pull llama3.2:1b"
            )
        else:
            reply = f"Ошибка: {e}"

    await update.message.reply_text(reply[:4000] if len(reply) > 4000 else reply)

    # В историю добавляем только успешные ответы LLM
    if reply_ok:
        if chat_id not in CHAT_HISTORY:
            CHAT_HISTORY[chat_id] = []
        CHAT_HISTORY[chat_id].append({"role": "user", "content": user_text})
        CHAT_HISTORY[chat_id].append({"role": "assistant", "content": reply})
        CHAT_HISTORY[chat_id] = CHAT_HISTORY[chat_id][-(HISTORY_LENGTH * 2) :]


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit(
            "Задай TELEGRAM_BOT_TOKEN в .env или в переменных окружения. "
            "Токен создаётся через @BotFather в Telegram."
        )

    async def post_init_callback(application: Application) -> None:
        logger.info("Бот запущен")

    app = (
        Application.builder()
        .token(token)
        .post_init(post_init_callback)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
