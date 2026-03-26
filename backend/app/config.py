# MindMesh v2 — Application Configuration
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    AI_PROVIDER: str = "auto"  # auto | openai | groq | gemini

    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4o-mini"

    GROQ_API_KEY: str | None = None
    GROQ_MODEL: str = "llama-3.1-8b-instant"

    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-2.0-flash"
    MONGODB_URL: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = "mindmesh_v2"
    SECRET_KEY: str = "mindmesh-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    class Config:
        env_file = ".env"

settings = Settings()
