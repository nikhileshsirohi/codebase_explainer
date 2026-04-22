def classify_intent(question: str) -> str:
    q = question.lower()

    if any(
        x in q
        for x in (
            "ask",
            "session",
            "chat",
            "conversation",
            "history",
            "rag",
            "answer",
            "response",
            "retriev",
        )
    ):
        return "api_flow"

    if any(
        x in q
        for x in (
            "ingestion flow",
            "ingest flow",
            "repo ingestion",
            "indexing flow",
            "end-to-end",
            "end to end",
            "pipeline",
            "how does ingestion",
            "how is repo ingested",
        )
    ):
        return "repo_ingestion"

    if any(x in q for x in ("fetch", "github", "blob", "file contents", "download", "tree", "repo files")):
        return "github_fetch"

    return "general"
