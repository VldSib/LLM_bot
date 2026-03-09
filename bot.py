import os
from collections import defaultdict
from typing import List, Any

import telebot
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI

from rag import build_knowledge_base, load_or_build_faiss_index, retrieve_context


load_dotenv()

OPENROUTER_BASE = "https://openrouter.ai/api/v1"
MODEL_NAME = "z-ai/glm-4.5-air:free"
MAX_HISTORY_MESSAGES = 20  # сколько последних сообщений диалога помнить

llm = ChatOpenAI(
    openai_api_key=os.getenv("OPENROUTER_API_KEY"),
    openai_api_base=OPENROUTER_BASE,
    model_name=MODEL_NAME,
)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

# история сообщений для каждого чата
chat_histories: dict[int, List[Any]] = defaultdict(list)

# in-memory база знаний для RAG
knowledge_chunks = build_knowledge_base()
# FAISS-индекс (эмбеддинги OpenRouter); при отсутствии — поиск по ключевым словам
faiss_store = load_or_build_faiss_index(knowledge_chunks)

SYSTEM_PROMPT = (
    "Ты дружелюбный русскоязычный помощник в Telegram. "
    "Веди себя как собеседник, помни контекст предыдущих сообщений "
    "и отвечай кратко и по делу."
)


@bot.message_handler(commands=["start", "help"])
def handle_start(message):
    bot.reply_to(
        message,
        "Привет! Я ИИ‑бот. Пиши мне сообщения — я буду отвечать, "
        "помня контекст нашей беседы.\n\n"
        "Для рабочих вопросов могу использовать локальную базу знаний из папки docs.",
    )


@bot.message_handler(func=lambda message: True)
def handle_llm_message(message):
    try:
        chat_id = message.chat.id
        history = chat_histories[chat_id]

        user_msg = HumanMessage(content=message.text)
        history.append(user_msg)

        # RAG: подбираем контекст (FAISS при наличии, иначе по ключевым словам)
        rag_context = retrieve_context(knowledge_chunks, message.text, vectorstore=faiss_store)

        messages_for_llm: List[Any] = [SystemMessage(content=SYSTEM_PROMPT)]
        if rag_context:
            messages_for_llm.append(SystemMessage(content=rag_context))

        messages_for_llm.extend(history[-MAX_HISTORY_MESSAGES:])

        print(f"[{chat_id}] USER:", message.text)

        response_msg = llm.invoke(messages_for_llm)
        response_text = response_msg.content

        print(f"[{chat_id}] BOT:", response_text)

        if isinstance(response_msg, AIMessage):
            history.append(response_msg)
        else:
            history.append(AIMessage(content=response_text))

        if len(history) > MAX_HISTORY_MESSAGES:
            chat_histories[chat_id] = history[-MAX_HISTORY_MESSAGES:]

        bot.reply_to(message, response_text)

    except Exception as e:
        bot.reply_to(message, f"Ошибка: {str(e)}. Попробуйте позже.")


bot.polling()
