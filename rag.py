"""
RAG: загрузка документов из папки docs и поиск релевантных фрагментов по запросу.
Поддерживается векторный поиск (FAISS + эмбеддинги OpenRouter) и fallback по ключевым словам.
"""
import os
from typing import List, Dict, Any, Optional

from pypdf import PdfReader
import docx

# Папка с базой знаний — docs внутри проекта (AI_YP/docs)
DOCS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "docs"))
# Путь к сохранённому индексу FAISS (относительно корня проекта)
FAISS_INDEX_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "rag_faiss_index"))
MAX_RAG_CONTEXT_CHARS = 6000
DEFAULT_TOP_K = 10

# Эмбеддинги через OpenRouter (тот же ключ, что для чата)
OPENROUTER_EMBEDDINGS_BASE = "https://openrouter.ai/api/v1"
EMBEDDING_MODEL = "openai/text-embedding-3-small"


def _split_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    chunks: List[str] = []
    start = 0
    length = len(text)
    if length == 0:
        return chunks

    while start < length:
        end = min(start + chunk_size, length)
        chunks.append(text[start:end])
        start += max(chunk_size - overlap, 1)
    return chunks


def _load_pdf(path: str) -> str:
    try:
        reader = PdfReader(path)
        pages_text = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages_text)
    except Exception as e:
        print(f"[RAG] Ошибка чтения PDF {path}: {e}")
        return ""


def _load_docx(path: str) -> str:
    try:
        document = docx.Document(path)
        return "\n".join(p.text for p in document.paragraphs)
    except Exception as e:
        print(f"[RAG] Ошибка чтения DOCX {path}: {e}")
        return ""


def build_knowledge_base(docs_dir: str | None = None) -> List[Dict[str, Any]]:
    """
    Простой in-memory RAG: режем документы из docs на куски,
    затем по запросу ищем по пересечению ключевых слов.
    """
    base_dir = docs_dir or DOCS_DIR
    chunks: List[Dict[str, Any]] = []
    files_added: List[str] = []
    files_skipped: List[str] = []  # формат не поддерживается
    files_failed: List[str] = []   # ошибка чтения или пустой текст

    if not os.path.isdir(base_dir):
        print(f"[RAG] Папка с базой знаний не найдена: {base_dir}")
        return chunks

    for root, _, files in os.walk(base_dir):
        for name in files:
            lower = name.lower()
            path = os.path.join(root, name)

            text = ""
            if lower.endswith(".pdf"):
                text = _load_pdf(path)
            elif lower.endswith(".docx"):
                text = _load_docx(path)
            else:
                files_skipped.append(name)
                continue

            if not text:
                files_failed.append(name)
                continue

            files_added.append(name)
            for part in _split_text(text):
                chunks.append(
                    {
                        "text": part,
                        "source": name,
                    }
                )

    print(f"[RAG] Добавлено в базу знаний: {len(files_added)} файлов, {len(chunks)} фрагментов.")
    for name in files_added:
        print(f"  — {name}")
    if files_skipped:
        print(f"[RAG] Пропущено (формат не поддерживается .pdf/.docx): {len(files_skipped)} — {', '.join(files_skipped)}")
    if files_failed:
        print(f"[RAG] Не загружено (ошибка или пустой текст): {len(files_failed)} — {', '.join(files_failed)}")
    return chunks


def get_embeddings():
    """Эмбеддинги через OpenRouter (OpenAI-совместимый API)."""
    try:
        from langchain_openai import OpenAIEmbeddings
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            return None
        return OpenAIEmbeddings(
            openai_api_key=api_key,
            openai_api_base=OPENROUTER_EMBEDDINGS_BASE,
            model=EMBEDDING_MODEL,
        )
    except Exception as e:
        print(f"[RAG] Эмбеддинги недоступны: {e}")
        return None


def build_faiss_index(
    knowledge_chunks: List[Dict[str, Any]],
    index_path: str = FAISS_INDEX_PATH,
) -> Optional[Any]:
    """Строит индекс FAISS из фрагментов и сохраняет на диск."""
    from langchain_community.vectorstores import FAISS
    from langchain_core.documents import Document

    embeddings = get_embeddings()
    if not embeddings or not knowledge_chunks:
        return None

    docs = [
        Document(page_content=c["text"], metadata={"source": c["source"]})
        for c in knowledge_chunks
    ]
    print("[RAG] Построение FAISS-индекса (эмбеддинги через OpenRouter)...")
    try:
        vectorstore = FAISS.from_documents(docs, embeddings)
        vectorstore.save_local(index_path)
        print(f"[RAG] FAISS-индекс сохранён: {index_path}")
        return vectorstore
    except Exception as e:
        print(f"[RAG] Ошибка построения FAISS: {e}")
        return None


def load_faiss_index(index_path: str = FAISS_INDEX_PATH) -> Optional[Any]:
    """Загружает индекс FAISS с диска."""
    from langchain_community.vectorstores import FAISS

    if not os.path.isdir(index_path):
        return None
    embeddings = get_embeddings()
    if not embeddings:
        return None
    try:
        return FAISS.load_local(index_path, embeddings, allow_dangerous_deserialization=True)
    except Exception as e:
        print(f"[RAG] Ошибка загрузки FAISS: {e}")
        return None


def load_or_build_faiss_index(knowledge_chunks: List[Dict[str, Any]]) -> Optional[Any]:
    """Загружает FAISS с диска или строит заново при отсутствии индекса."""
    store = load_faiss_index()
    if store is not None:
        print("[RAG] Используется FAISS-индекс (семантический поиск).")
        return store
    return build_faiss_index(knowledge_chunks)


def _normalize_word(w: str) -> str:
    return "".join(c for c in w.lower() if c.isalnum() or c in "ё-")


def _score_chunk(query_tokens: List[str], chunk_text: str) -> int:
    """Оценка релевантности: точное вхождение слова + вхождение как подстроки в словах (для разных форм)."""
    text_lower = chunk_text.lower()
    chunk_words = [_normalize_word(w) for w in text_lower.split() if len(w) > 1]
    score = 0
    for token in query_tokens:
        if not token:
            continue
        t = _normalize_word(token)
        if len(t) < 2:
            continue
        if t in text_lower:
            score += 2
        elif any(t in w or w in t for w in chunk_words):
            score += 1
    return score


def _fallback_chunks(chunks: List[Dict[str, Any]], n: int = 5) -> List[Dict[str, Any]]:
    """При отсутствии совпадений — берём по одному фрагменту из разных файлов."""
    seen_sources: set[str] = set()
    result: List[Dict[str, Any]] = []
    for c in chunks:
        if c["source"] not in seen_sources and len(result) < n:
            result.append(c)
            seen_sources.add(c["source"])
        if len(result) >= n:
            break
    if len(result) < n:
        for c in chunks:
            if c not in result and len(result) < n:
                result.append(c)
    return result


def retrieve_context(
    knowledge_chunks: List[Dict[str, Any]],
    query: str,
    k: int | None = None,
    max_chars: int | None = None,
    vectorstore: Optional[Any] = None,
) -> str:
    """
    Поиск: при переданном vectorstore (FAISS) — семантический поиск по эмбеддингам;
    иначе по ключевым словам и подстрокам с fallback по разным файлам.
    """
    k = k if k is not None else DEFAULT_TOP_K
    limit = max_chars or MAX_RAG_CONTEXT_CHARS

    if vectorstore is not None:
        try:
            docs = vectorstore.similarity_search(query, k=k)
            context_parts = []
            total_len = 0
            for idx, doc in enumerate(docs, start=1):
                source = doc.metadata.get("source", "?")
                part = f"[{idx}] ({source})\n{doc.page_content}\n"
                if total_len + len(part) > limit:
                    break
                context_parts.append(part)
                total_len += len(part)
            if context_parts:
                header = (
                    "Вот выдержки из локальной базы знаний (документы из папки docs). "
                    "Отвечай, опираясь прежде всего на них. Если информации недостаточно, "
                    "честно скажи, чего не хватает.\n\n"
                )
                return header + "\n\n".join(context_parts)
        except Exception as e:
            print(f"[RAG] Ошибка FAISS-поиска, fallback на ключевые слова: {e}")

    if not knowledge_chunks:
        return ""

    tokens = [w for t in query.split() if t.strip() for w in [_normalize_word(t)] if len(w) >= 2]
    scored: List[tuple[int, Dict[str, Any]]] = []
    for chunk in knowledge_chunks:
        score = _score_chunk(tokens, chunk["text"])
        scored.append((score, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)
    if scored and scored[0][0] > 0:
        top_chunks = [c for _, c in scored[:k]]
    else:
        top_chunks = _fallback_chunks(knowledge_chunks, n=k)

    context_parts = []
    total_len = 0
    for idx, chunk in enumerate(top_chunks, start=1):
        part = f"[{idx}] ({chunk['source']})\n{chunk['text']}\n"
        if total_len + len(part) > limit:
            break
        context_parts.append(part)
        total_len += len(part)

    if not context_parts:
        return ""

    header = (
        "Вот выдержки из локальной базы знаний (документы из папки docs). "
        "Отвечай, опираясь прежде всего на них. Если информации недостаточно, "
        "честно скажи, чего не хватает.\n\n"
    )
    return header + "\n\n".join(context_parts)
