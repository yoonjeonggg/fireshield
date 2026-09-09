from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    law_api_key: str
    law_api_base_url: str
    encryption_key: str
    cors_origins: str = "http://localhost:3000"
    admin_api_key: str

    # --- AI(로컬 LLM) 사기 판정 ---
    ai_enabled: bool = True
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma2:2b"
    ai_timeout_seconds: float = 15.0
    ollama_keep_alive: str = "30m"  # 모델을 메모리에 유지하는 시간 (콜드스타트 방지)
    ai_conflict_gap: int = 45  # 규칙 점수와 이 폭 이상 벌어지면 AI 값을 폐기

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]


settings = Settings()