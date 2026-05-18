"""
核心配置模块：读取环境变量，统一管理应用配置
"""
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    ENV: str = "development"
    DATABASE_URL: str = "sqlite:///./taskflow.db"
    SECRET_KEY: str = "dev-secret-key"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    MAX_TASKS_PER_USER: int = 100

settings = Settings()
