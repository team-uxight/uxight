from pydantic import PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    db_url: str
    log_dir: str  # 스텝 로그 루트. 페르소나마다 <log_dir>/<run_id>/<persona_id>/steps.jsonl
    # 프로세스 전체에서 동시에 도는 Persona(= 브라우저) 수 상한. 모든 회차가 나눠 쓴다.
    max_concurrent_personas: PositiveInt = 3
