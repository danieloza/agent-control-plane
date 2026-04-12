from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(slots=True)
class Settings:
    app_name: str = "agent-control-plane"
    app_env: str = "development"
    database_url: str = "postgresql+psycopg://agent:agent@localhost:5432/agent_control_plane"
    log_level: str = "INFO"
    default_operator_profile: str = "ops-supervisor"
    jwt_secret: str = "agent-control-plane-dev-secret"
    jwt_algorithm: str = "HS256"
    jwt_exp_minutes: int = 60
    rate_limit_per_minute: int = 30


def get_settings() -> Settings:
    return Settings(
        app_name=os.getenv("APP_NAME", "agent-control-plane"),
        app_env=os.getenv("APP_ENV", "development"),
        database_url=os.getenv("DATABASE_URL", "postgresql+psycopg://agent:agent@localhost:5432/agent_control_plane"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        default_operator_profile=os.getenv("DEFAULT_OPERATOR_PROFILE", "ops-supervisor"),
        jwt_secret=os.getenv("JWT_SECRET", "agent-control-plane-dev-secret"),
        jwt_algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
        jwt_exp_minutes=int(os.getenv("JWT_EXP_MINUTES", "60")),
        rate_limit_per_minute=int(os.getenv("RATE_LIMIT_PER_MINUTE", "30")),
    )
