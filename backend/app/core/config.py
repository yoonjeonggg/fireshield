from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    law_api_key: str
    law_api_base_url: str
    encryption_key: str
    cors_origins: str = "http://localhost:3000"
    admin_api_key: str
    db_echo: bool = False  # True면 모든 SQL과 파라미터를 로그로 출력 (개발용)

    # --- AI(로컬 LLM) 사기 판정 ---
    ai_enabled: bool = True
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma2:2b"
    ai_timeout_seconds: float = 15.0
    ollama_keep_alive: str = "30m"  # 모델을 메모리에 유지하는 시간 (콜드스타트 방지)
    # CPU 추론 스레드 수. 비우면 Ollama 기본값(물리 코어 수 기준)을 쓴다.
    ollama_num_thread: int | None = None
    ai_conflict_gap: int = 45  # 규칙 점수와 이 폭 이상 벌어지면 AI 값을 폐기

    # 계좌 사기 신고 이력 조회 — 경찰청 기준(최근 3개월/3회 이상)을 따름
    fraud_check_window_days: int = 90
    fraud_check_report_threshold: int = 3

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]


settings = Settings()