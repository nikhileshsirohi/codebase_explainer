from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "codebase-explainer-api"
    ENV: str = "dev"

    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGODB_DB: str = "codebase_explainer"

    GITHUB_TOKEN: str | None = None
    GEMINI_API_KEY: str | None = None
    EMBEDDING_DIM: int = 768 #1536
    MONGODB_VECTOR_INDEX: str = "code_chunks_v1"

    EMBEDDING_PROVIDER: str = "ollama" 
    OLLAMA_EMBED_MODEL: str = "nomic-embed-text"

    GEMINI_CHAT_MODEL: str = "gemini-2.0-flash"
    CHAT_HISTORY_MAX_TURNS: int = 6

    LLM_PROVIDER: str = "auto"  # auto | gemini | local | ollama
    LOCAL_LLM_MODEL: str = "google/flan-t5-base"
    OLLAMA_MODEL: str = "qwen2.5-coder:7b-instruct"
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    INGEST_TIMEOUT_MINUTES: int = 15

settings = Settings()