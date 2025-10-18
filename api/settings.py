# from pydantic import BaseSettings
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    OPENAI_API_KEY: str
    MODEL_DEFAULT: str = "gpt-4o"
    KG_PATH: str = ""
    class Config:
        env_file = ".env"

settings = Settings()

