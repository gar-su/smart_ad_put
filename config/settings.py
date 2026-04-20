from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # 项目根目录
    BASE_DIR: Path = Path(__file__).resolve().parent.parent

    # 数据库
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/smart_ad_put"

    # Hive 数仓
    HIVE_HOST: str = "localhost"
    HIVE_PORT: int = 10000
    HIVE_DATABASE: str = "default"
    HIVE_AUTH: str = "plain"

    # 决策日志
    DECISION_LOG_DIR: Path = BASE_DIR / "logs" / "decisions"

    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # 数据轮询间隔（秒）
    POLL_INTERVAL_SECONDS: int = 300

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
