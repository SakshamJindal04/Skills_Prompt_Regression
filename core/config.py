"""
Enterprise Configuration Settings (Pydantic v2).
Provides strongly typed environment and policy settings with helpful validation error messages.
"""

import os
from pathlib import Path
from typing import List, Optional
from pydantic import Field, field_validator, ValidationInfo
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class AppSettings(BaseSettings):
    """
    Pydantic v2 validated settings loaded from environment variables and policy.yaml.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    db_url: str = Field(
        default="mysql+pymysql://regression_user:regression_pass@localhost:3306/regression_db",
        description="Database connection string for MySQL or SQLite.",
    )
    fallback_sqlite_url: str = Field(
        default="sqlite:///regression_manager.db",
        description="Fallback SQLite connection string.",
    )

    # Runtime Environment
    environment: str = Field(
        default="dev",
        description="Active deployment environment: dev, staging, or prod.",
    )

    # Statistical Evaluation Parameters
    alpha: float = Field(
        default=0.05,
        description="Significance level alpha for exact McNemar test.",
    )
    k: int = Field(
        default=5,
        description="Number of repetitions per test case for majority voting (must be odd).",
    )
    active_decision_rule: str = Field(
        default="mcnemar_exact",
        description="Active decision rule variant: mcnemar_exact, non_inferiority, holm_bonferroni, odds_ratio.",
    )
    non_inferiority_margin: float = Field(
        default=0.05,
        description="Permitted non-inferiority margin delta for Rule (b).",
    )
    odds_ratio_threshold: float = Field(
        default=1.5,
        description="Maximum permissible discordant odds ratio for Rule (d).",
    )

    # Model & Security
    allowed_models: List[str] = Field(
        default_factory=lambda: [
            "qwen2.5:3b",
            "qwen2.5:7b",
            "qwen2.5:latest",
            "llama3.2:3b",
            "gemma2:2b",
            "qwen3:4b",
        ]
    )
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Base URL for local Ollama daemon.",
    )
    api_host: str = Field(
        default="127.0.0.1",
        description="Local host binding for REST API (never bind 0.0.0.0 in local-first mode).",
    )
    api_port: int = Field(
        default=8000,
        description="Port for local REST API.",
    )

    @field_validator("alpha")
    @classmethod
    def validate_alpha(cls, v: float) -> float:
        if not (0.0 < v < 1.0):
            raise ValueError(f"Alpha significance level must be between 0.0 and 1.0 (got {v}).")
        return v

    @field_validator("k")
    @classmethod
    def validate_k(cls, v: int) -> int:
        if v < 1:
            raise ValueError(f"Repetitions k must be at least 1 (got {v}).")
        if v % 2 == 0:
            raise ValueError(f"Repetitions k must be an odd integer to prevent majority voting ties (got {v}).")
        return v

    @field_validator("active_decision_rule")
    @classmethod
    def validate_decision_rule(cls, v: str) -> str:
        valid_rules = {"mcnemar_exact", "non_inferiority", "holm_bonferroni", "odds_ratio"}
        clean = v.strip().lower()
        if clean not in valid_rules:
            raise ValueError(
                f"Invalid decision rule '{v}'. Must be one of: {sorted(list(valid_rules))}."
            )
        return clean

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        valid_envs = {"dev", "staging", "prod"}
        clean = v.strip().lower()
        if clean not in valid_envs:
            raise ValueError(
                f"Invalid environment '{v}'. Must be one of: {sorted(list(valid_envs))}."
            )
        return clean

    @field_validator("non_inferiority_margin")
    @classmethod
    def validate_margin(cls, v: float) -> float:
        if v <= 0:
            raise ValueError(f"Non-inferiority margin must be positive (got {v}).")
        return v


_settings_instance: Optional[AppSettings] = None


def get_settings() -> AppSettings:
    """Returns singleton validated application settings instance."""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = AppSettings()
    return _settings_instance
