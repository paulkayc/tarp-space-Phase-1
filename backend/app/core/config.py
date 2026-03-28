from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_env: str = "development"
    app_port: int = 8000

    # Database
    database_url: str = "postgresql://tarpspace:tarpspace@localhost:5432/tarpspace"

    # Local dev auth
    dev_auth_token: str = "dev-token-local"
    admin_api_key: str = "admin-local"

    # Cloud auth — Clerk (leave blank for local dev)
    # TODO: populate when auth provider is finalised.
    # ARCHITECTURE.md references Supabase; CONTRACTS.md references Clerk.
    # Only one set of keys will be used in production.
    clerk_secret_key: str = ""
    clerk_publishable_key: str = ""

    # Cloud auth — Supabase alternative (leave blank if using Clerk)
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""

    # AI / Embedding
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536
    llm_model: str = "claude-opus-4-6"
    llm_max_tokens: int = 1000
    llm_max_history_turns: int = 10

    # Matching
    escalation_threshold_pct: float = 0.15
    match_top_n: int = 5
    match_radius_default_m: int = 8046

    # Completeness
    completeness_threshold: float = 0.7
    onboarding_completeness_threshold: float = 0.7

    # Logging / Alerting
    log_level: str = "INFO"
    llm_cost_alert_threshold_usd: float = 0.05


settings = Settings()
