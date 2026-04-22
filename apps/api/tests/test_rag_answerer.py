from app.services.rag.answerer import (
    _intent_profile,
    _question_keywords,
    _rank_candidate,
)
from app.services.rag.intent import classify_intent


def test_classify_intent_detects_rag_flow_queries():
    assert classify_intent("How does the RAG answer pipeline work?") == "api_flow"


def test_question_keywords_prioritize_meaningful_terms():
    keywords = _question_keywords(
        "Explain how the ask response pipeline works in app/services/rag/answerer.py",
        extra=["chat", "sources"],
    )

    assert "ask" in keywords
    assert "app/services/rag/answerer.py" in keywords
    assert "sources" in keywords
    assert "how" not in keywords
    assert "the" not in keywords


def test_rank_candidate_prefers_path_and_text_matches():
    profile = _intent_profile("api_flow")
    keywords = _question_keywords("How does ask_repo generate an answer?", extra=profile["keywords"])

    chat_row = {
        "path": "app/api/v1/chat.py",
        "text": "async def ask_repo(...): rag = await generate_answer(...)",
        "score": 0.52,
    }
    indexing_row = {
        "path": "app/services/indexing/indexer.py",
        "text": "build embeddings and chunk repository files",
        "score": 0.79,
    }

    chat_score = _rank_candidate(chat_row, keywords=keywords, path_hints=profile["path_hints"])
    indexing_score = _rank_candidate(indexing_row, keywords=keywords, path_hints=profile["path_hints"])

    assert chat_score > indexing_score
