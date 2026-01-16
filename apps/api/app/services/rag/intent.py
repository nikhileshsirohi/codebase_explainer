def classify_intent(question: str) -> str:
    q = question.lower()

    if any(x in q for x in ("ingestion flow", "ingest flow", "repo ingestion", "end-to-end", "pipeline")):
        return "repo_ingestion"

    if any(x in q for x in ("ask", "session", "chat", "conversation", "history")):
        return "api_flow"

    if any(x in q for x in ("fetch", "github", "blob", "file contents", "download")):
        return "github_fetch"

    return "general"