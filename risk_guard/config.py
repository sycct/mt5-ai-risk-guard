from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .models import RiskLevel


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    mt5_mcp_url: str = "http://127.0.0.1:22346/mcp"
    mt5_mcp_api_key: str | None = None
    mt5_mcp_auth_header: str = "Authorization"
    mt5_mcp_auth_scheme: str = "Bearer"
    mt5_mcp_timeout_seconds: float = 15.0
    mt5_mcp_debug: bool = False

    deepseek_api_key: str | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-v4-flash"
    ai_analysis_enabled: bool = True
    ai_on_risk_change: bool = True
    ai_min_risk_level: RiskLevel = RiskLevel.WARNING
    ai_cooldown_minutes: int = Field(default=60, ge=1)

    mt5_symbol: str = "XAUUSD"
    ea_magic: int = 9527
    log_dir: Path = Path("logs")
    report_dir: Path = Path("reports")

    dry_run: bool = True
    trade_actions_enabled: bool = False
    allow_close_positions: bool = False
    allow_delete_orders: bool = False
    allow_pause_ea: bool = False
    max_allowed_actions_per_hour: int = Field(default=0, ge=0)
    shadow_mode_enabled: bool = True
    shadow_confirmation_checks: int = Field(default=2, ge=1)

    caution_drawdown: float = 3
    warning_drawdown: float = 5
    danger_drawdown: float = 8
    emergency_drawdown: float = 10

    @field_validator("ai_min_risk_level", mode="before")
    @classmethod
    def parse_ai_min_risk_level(cls, value):
        if isinstance(value, str):
            normalized = value.strip().upper()
            try:
                return RiskLevel[normalized]
            except KeyError:
                pass
        return value

    @model_validator(mode="after")
    def enforce_phase_one_read_only(self) -> "Settings":
        # Phase one contains no action implementation. Reject unsafe configuration.
        if self.trade_actions_enabled:
            raise ValueError("第一阶段不支持交易动作；请保持 TRADE_ACTIONS_ENABLED=false")
        return self

    def auth_headers(self) -> dict[str, str]:
        if not self.mt5_mcp_api_key:
            return {}
        value = self.mt5_mcp_api_key
        if self.mt5_mcp_auth_scheme:
            value = f"{self.mt5_mcp_auth_scheme} {value}"
        return {self.mt5_mcp_auth_header: value}


@lru_cache
def get_settings() -> Settings:
    return Settings()
