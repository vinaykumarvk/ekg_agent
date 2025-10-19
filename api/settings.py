# from pydantic import BaseSettings
from pydantic_settings import BaseSettings
from pydantic import validator
import os

class Settings(BaseSettings):
    OPENAI_API_KEY: str
    MODEL_DEFAULT: str = "gpt-4o"
    KG_PATH: str = ""
    CACHE_DIR: str = "/tmp/ekg_cache"
    LOG_LEVEL: str = "INFO"
    MAX_CACHE_SIZE: int = 1000
    CACHE_TTL: int = 3600
    
    @validator('OPENAI_API_KEY')
    def validate_openai_key(cls, v):
        if not v or not v.startswith('sk-'):
            raise ValueError('Invalid OpenAI API key format')
        return v
    
    @validator('LOG_LEVEL')
    def validate_log_level(cls, v):
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f'Invalid log level. Must be one of: {valid_levels}')
        return v.upper()
    
    @validator('MAX_CACHE_SIZE')
    def validate_cache_size(cls, v):
        if v < 10 or v > 10000:
            raise ValueError('MAX_CACHE_SIZE must be between 10 and 10000')
        return v
    
    @validator('CACHE_TTL')
    def validate_cache_ttl(cls, v):
        if v < 60 or v > 86400:  # 1 minute to 24 hours
            raise ValueError('CACHE_TTL must be between 60 and 86400 seconds')
        return v
    
    model_config = {
        "env_file": ".env",
        "extra": "ignore"
    }

settings = Settings()

