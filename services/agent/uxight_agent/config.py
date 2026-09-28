from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    db_url: str
    log_dir: str  # 스텝 로그 루트. 런마다 <log_dir>/<run_id>/steps.jsonl
