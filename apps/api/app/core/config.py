from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "codebase-explainer-api"
    ENV: str = "dev"

    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGODB_DB: str = "codebase_explainer"

    GITHUB_TOKEN: str | None = None

settings = Settings()