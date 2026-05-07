"""
Strategy Intermediate Representation (IR) models.
This is the core data structure that represents a trading strategy
in a format that can be understood by the backtester, mutator, and MT5 generator.
"""
from __future__ import annotations
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class StrategyType(str, Enum):
    TREND_FOLLOWING = "trend_following"
    MEAN_REVERSION = "mean_reversion"
    BREAKOUT = "breakout"
    SCALPING = "scalping"
    SWING = "swing"
    ARBITRAGE = "arbitrage"
    OPTIONS = "options"
    CUSTOM = "custom"


class Timeframe(str, Enum):
    M1 = "M1"
    M5 = "M5"
    M15 = "M15"
    M30 = "M30"
    H1 = "H1"
    H4 = "H4"
    D1 = "D1"
    W1 = "W1"
    MN1 = "MN1"


class IndicatorType(str, Enum):
    # Trend
    SMA = "sma"
    EMA = "ema"
    WMA = "wma"
    HMA = "hma"
    ICHIMOKU = "ichimoku"
    ADX = "adx"
    SUPERTREND = "supertrend"
    # Momentum
    RSI = "rsi"
    MACD = "macd"
    STOCHASTIC = "stochastic"
    CCI = "cci"
    WILLIAMS_R = "williams_r"
    MFI = "mfi"
    # Volatility
    BOLLINGER_BANDS = "bollinger_bands"
    ATR = "atr"
    KELTNER_CHANNEL = "keltner_channel"
    DONCHIAN_CHANNEL = "donchian_channel"
    # Volume
    VOLUME = "volume"
    OBV = "obv"
    VWAP = "vwap"
    ADL = "adl"
    # Custom
    CUSTOM = "custom"


class Indicator(BaseModel):
    type: IndicatorType
    parameters: Dict[str, Any] = Field(default_factory=dict)
    # e.g. for SMA: {"period": 20}
    # e.g. for RSI: {"period": 14, "overbought": 70, "oversold": 30}
    # e.g. for BollingerBands: {"period": 20, "std_dev": 2.0}


class ConditionOperator(str, Enum):
    GREATER_THAN = ">"
    LESS_THAN = "<"
    EQUAL = "=="
    GREATER_EQUAL = ">="
    LESS_EQUAL = "<="
    CROSSES_ABOVE = "crosses_above"
    CROSSES_BELOW = "crosses_below"
    BETWEEN = "between"
    OUTSIDE = "outside"


class Condition(BaseModel):
    left_operand: str  # e.g. "close", "rsi(14)", "sma(20)"
    operator: ConditionOperator
    right_operand: str  # e.g. "sma(50)", "70", "upper_bb"
    indicator_ref: Optional[str] = None  # reference to an indicator by name


class ConditionGroup(BaseModel):
    """A group of conditions combined with AND/OR logic."""
    logic: str = "AND"  # "AND" or "OR"
    conditions: List[Condition] = Field(default_factory=list)
    sub_groups: List[ConditionGroup] = Field(default_factory=list)


class SignalType(str, Enum):
    BUY = "buy"
    SELL = "sell"
    CLOSE_LONG = "close_long"
    CLOSE_SHORT = "close_short"
    CLOSE_ALL = "close_all"


class Signal(BaseModel):
    type: SignalType
    condition: ConditionGroup
    confidence: float = 1.0  # 0.0 to 1.0


class RiskManagement(BaseModel):
    stop_loss: Optional[float] = None  # in pips or percentage
    stop_loss_type: str = "fixed"  # "fixed", "atr_based", "percentage"
    take_profit: Optional[float] = None
    take_profit_type: str = "fixed"
    trailing_stop: Optional[float] = None
    trailing_stop_type: str = "fixed"
    max_position_size: float = 1.0  # in lots or percentage of equity
    max_position_size_type: str = "lots"  # "lots", "percentage"
    max_drawdown_limit: Optional[float] = None  # percentage
    risk_per_trade: Optional[float] = None  # percentage of equity
    max_open_positions: int = 1
    max_daily_trades: Optional[int] = None
    max_daily_loss: Optional[float] = None


class StrategyIR(BaseModel):
    """
    Intermediate Representation of a trading strategy.
    This is the universal format that all components understand.
    """
    name: str = "Untitled Strategy"
    description: str = ""
    type: StrategyType = StrategyType.CUSTOM
    version: str = "1.0"

    # Market context
    instruments: List[str] = Field(default_factory=lambda: ["EURUSD"])
    timeframes: List[Timeframe] = Field(default_factory=lambda: [Timeframe.H1])

    # Strategy components
    indicators: List[Indicator] = Field(default_factory=list)
    entry_signals: List[Signal] = Field(default_factory=list)
    exit_signals: List[Signal] = Field(default_factory=list)
    risk_management: RiskManagement = Field(default_factory=RiskManagement)

    # Metadata
    tags: List[str] = Field(default_factory=list)
    source_idea: str = ""  # original natural language idea
    created_at: str = ""
    mutated_from: Optional[str] = None  # parent strategy ID
    mutation_generation: int = 0

    def to_dict(self) -> dict:
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict) -> StrategyIR:
        return cls(**data)

    def summary(self) -> str:
        lines = [
            f"Strategy: {self.name}",
            f"Type: {self.type.value}",
            f"Instruments: {', '.join(self.instruments)}",
            f"Timeframes: {', '.join(t.value for t in self.timeframes)}",
            f"Indicators: {len(self.indicators)}",
            f"Entry signals: {len(self.entry_signals)}",
            f"Exit signals: {len(self.exit_signals)}",
        ]
        if self.risk_management.stop_loss:
            lines.append(f"Stop Loss: {self.risk_management.stop_loss}")
        if self.risk_management.take_profit:
            lines.append(f"Take Profit: {self.risk_management.take_profit}")
        return "\n".join(lines)
