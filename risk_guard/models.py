from datetime import datetime, timezone
from enum import IntEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RiskLevel(IntEnum):
    DATA_UNAVAILABLE = -1
    OK = 0
    CAUTION = 1
    WARNING = 2
    DANGER = 3
    EMERGENCY = 4

    def __str__(self) -> str:
        return self.name


class ToolInfo(BaseModel):
    name: str
    description: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict, alias="inputSchema")
    model_config = ConfigDict(populate_by_name=True, extra="allow")


class ResourceInfo(BaseModel):
    uri: str
    name: str = ""
    description: str = ""
    mime_type: str | None = Field(None, alias="mimeType")
    model_config = ConfigDict(populate_by_name=True, extra="allow")


class Account(BaseModel):
    login: str | int | None = None
    server: str | None = None
    balance: float | None = None
    equity: float | None = None
    margin: float | None = None
    free_margin: float | None = None
    margin_level: float | None = None
    currency: str | None = None


class SymbolInfo(BaseModel):
    symbol: str
    bid: float | None = None
    ask: float | None = None
    spread: float | None = None
    digits: int | None = None
    point: float | None = None
    volume_min: float | None = None
    volume_step: float | None = None
    stops_level: int | None = None
    freeze_level: int | None = None


class Position(BaseModel):
    ticket: str | int | None = None
    symbol: str | None = None
    type: Literal["buy", "sell", "unknown"] = "unknown"
    volume: float = 0
    open_price: float | None = None
    current_price: float | None = None
    profit: float = 0
    swap: float | None = None
    commission: float | None = None
    magic: int | None = None
    comment: str | None = None
    open_time: datetime | str | int | None = None

    @field_validator("type", mode="before")
    @classmethod
    def normalize_side(cls, value: Any) -> str:
        if value in (0, "0") or str(value).lower() in ("buy", "long", "position_type_buy"):
            return "buy"
        if value in (1, "1") or str(value).lower() in ("sell", "short", "position_type_sell"):
            return "sell"
        return "unknown"


class PendingOrder(BaseModel):
    ticket: str | int | None = None
    symbol: str | None = None
    type: str = "unknown"
    volume: float = 0
    price: float | None = None
    magic: int | None = None
    comment: str | None = None
    create_time: datetime | str | int | None = None


class HistorySummary(BaseModel):
    today_closed_profit: float | None = None
    today_gross_profit: float | None = None
    today_gross_loss: float | None = None
    today_trade_count: int | None = None


class Mt5Snapshot(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    account: Account = Field(default_factory=Account)
    symbol: SymbolInfo | None = None
    positions: list[Position] = Field(default_factory=list)
    pending_orders: list[PendingOrder] = Field(default_factory=list)
    history: HistorySummary | None = None
    missing_capabilities: list[str] = Field(default_factory=list)


class RiskMetrics(BaseModel):
    balance: float | None = None
    equity: float | None = None
    floating_profit: float
    equity_drawdown_money: float | None = None
    equity_drawdown_percent: float | None = None
    margin_level: float | None = None
    spread: float | None = None
    buy_lots: float
    sell_lots: float
    total_lots: float
    net_lots: float
    buy_positions_count: int
    sell_positions_count: int
    total_positions_count: int
    pending_orders_count: int
    buy_profit: float
    sell_profit: float
    worse_side: Literal["buy", "sell", "neutral"]
    net_direction: Literal["long", "short", "neutral"]
    ea_positions_count: int
    ea_position_lots: float
    ea_pending_orders_count: int
    non_ea_positions_count: int
    non_ea_pending_orders_count: int


class RuleHit(BaseModel):
    level: RiskLevel
    metric: str
    value: float
    threshold: float
    message: str


class RiskAssessment(BaseModel):
    level: RiskLevel
    metrics: RiskMetrics
    hard_rule_hits: list[RuleHit] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)


class AiRiskReport(BaseModel):
    risk_level: RiskLevel
    summary: str
    main_risks: list[str]
    recommended_actions: list[str]
    do_not_do: list[str]
    reasoning_brief: str

    @field_validator("risk_level", mode="before")
    @classmethod
    def parse_level_name(cls, value: Any) -> Any:
        if isinstance(value, str):
            aliases = {"LOW": RiskLevel.OK, "MEDIUM": RiskLevel.CAUTION,
                       "HIGH": RiskLevel.WARNING, "CRITICAL": RiskLevel.DANGER}
            if value.upper() in aliases:
                return aliases[value.upper()]
            try:
                return RiskLevel[value.upper()]
            except KeyError:
                return value
        return value
