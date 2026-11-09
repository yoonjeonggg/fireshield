from pydantic import model_validator
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

    # /verify 요청 횟수 제한 — 클라이언트(IP)당 1분 동안 허용하는 요청 수. 0이면 끈다.
    verify_rate_limit_per_minute: int = 10
    # 리버스 프록시 뒤에서 운영할 때만 True. 프록시가 덧붙인 X-Forwarded-For의
    # 마지막 값을 클라이언트 IP로 쓴다. (직접 노출된 서버에서 켜면 IP를 위조할 수 있음)
    trust_forwarded_for: bool = False

    # 진위확인 로그(암호화된 계좌번호 포함) 보관 기간. 이 기간이 지난 로그는 자동 삭제한다.
    # 계좌 사기 이력 집계 기간(fraud_check_window_days)보다 짧으면 집계가 깨지므로 그 이상이어야 한다.
    verify_log_retention_days: int = 180

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    @model_validator(mode="after")
    def _check_retention_covers_fraud_window(self):
        if self.verify_log_retention_days < self.fraud_check_window_days:
            raise ValueError(
                "VERIFY_LOG_RETENTION_DAYS는 FRAUD_CHECK_WINDOW_DAYS 이상이어야 합니다 "
                f"({self.verify_log_retention_days} < {self.fraud_check_window_days})"
            )
        return self

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]


settings = Settings()