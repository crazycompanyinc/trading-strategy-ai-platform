"""
Strategy Parser - Converts natural language + images into Strategy IR.
Uses LLM for NLP understanding and image analysis.
"""
from __future__ import annotations
import json
import re
from typing import Optional, List, Dict, Any

from strategy.models import (
    StrategyIR, StrategyType, Timeframe, Indicator, IndicatorType,
    Signal, SignalType, Condition, ConditionGroup, ConditionOperator,
    RiskManagement
)


# Known indicator keywords for quick matching
INDICATOR_KEYWORDS = {
    "sma": IndicatorType.SMA, "simple moving average": IndicatorType.SMA,
    "ema": IndicatorType.EMA, "exponential moving average": IndicatorType.EMA,
    "wma": IndicatorType.WMA, "weighted moving average": IndicatorType.WMA,
    "hma": IndicatorType.HMA, "hull moving average": IndicatorType.HMA,
    "rsi": IndicatorType.RSI, "relative strength index": IndicatorType.RSI,
    "macd": IndicatorType.MACD,
    "bollinger": IndicatorType.BOLLINGER_BANDS, "bollinger bands": IndicatorType.BOLLINGER_BANDS, "bb": IndicatorType.BOLLINGER_BANDS,
    "atr": IndicatorType.ATR, "average true range": IndicatorType.ATR,
    "stochastic": IndicatorType.STOCHASTIC, "stoch": IndicatorType.STOCHASTIC,
    "cci": IndicatorType.CCI, "commodity channel index": IndicatorType.CCI,
    "adx": IndicatorType.ADX, "average directional index": IndicatorType.ADX,
    "ichimoku": IndicatorType.ICHIMOKU,
    "supertrend": IndicatorType.SUPERTREND,
    "vwap": IndicatorType.VWAP, "volume weighted average price": IndicatorType.VWAP,
    "obv": IndicatorType.OBV, "on balance volume": IndicatorType.OBV,
    "mfi": IndicatorType.MFI, "money flow index": IndicatorType.MFI,
    "williams": IndicatorType.WILLIAMS_R, "williams %r": IndicatorType.WILLIAMS_R,
    "donchian": IndicatorType.DONCHIAN_CHANNEL, "donchian channel": IndicatorType.DONCHIAN_CHANNEL,
    "keltner": IndicatorType.KELTNER_CHANNEL, "keltner channel": IndicatorType.KELTNER_CHANNEL,
    "volume": IndicatorType.VOLUME,
}

STRATEGY_TYPE_KEYWORDS = {
    "trend following": StrategyType.TREND_FOLLOWING, "trend": StrategyType.TREND_FOLLOWING,
    "seguir tendencia": StrategyType.TREND_FOLLOWING, "seguimiento de tendencia": StrategyType.TREND_FOLLOWING,
    "mean reversion": StrategyType.MEAN_REVERSION, "reversion": StrategyType.MEAN_REVERSION, "reversión": StrategyType.MEAN_REVERSION,
    "breakout": StrategyType.BREAKOUT, "ruptura": StrategyType.BREAKOUT,
    "scalping": StrategyType.SCALPING, "scalp": StrategyType.SCALPING,
    "swing": StrategyType.SWING, "swing trading": StrategyType.SWING,
}

TIMEFRAME_KEYWORDS = {
    "1m": Timeframe.M1, "m1": Timeframe.M1, "1 minute": Timeframe.M1,
    "5m": Timeframe.M5, "m5": Timeframe.M5, "5 minute": Timeframe.M5,
    "15m": Timeframe.M15, "m15": Timeframe.M15, "15 minute": Timeframe.M15,
    "30m": Timeframe.M30, "m30": Timeframe.M30, "30 minute": Timeframe.M30,
    "1h": Timeframe.H1, "h1": Timeframe.H1, "hourly": Timeframe.H1, "1 hour": Timeframe.H1,
    "4h": Timeframe.H4, "h4": Timeframe.H4, "4 hour": Timeframe.H4,
    "daily": Timeframe.D1, "d1": Timeframe.D1, "1d": Timeframe.D1, "day": Timeframe.D1,
    "weekly": Timeframe.W1, "w1": Timeframe.W1, "1w": Timeframe.W1,
}


class StrategyParser:
    """
    Parses natural language trading descriptions into structured StrategyIR.
    Uses keyword extraction + heuristic parsing. The LLM agent handles
    complex reasoning; this class handles the structured extraction.
    """

    def parse(self, text: str, images: Optional[List[str]] = None) -> StrategyIR:
        """
        Parse natural language text into a StrategyIR.
        
        Args:
            text: Natural language description of the trading strategy
            images: Optional list of base64-encoded images
            
        Returns:
            StrategyIR object
        """
        text_lower = text.lower()

        # Extract strategy type
        strategy_type = self._extract_strategy_type(text_lower)

        # Extract instruments
        instruments = self._extract_instruments(text)

        # Extract timeframes
        timeframes = self._extract_timeframes(text_lower)

        # Extract indicators
        indicators = self._extract_indicators(text_lower)

        # Extract entry signals
        entry_signals = self._extract_entry_signals(text_lower, indicators)

        # Extract exit signals
        exit_signals = self._extract_exit_signals(text_lower, indicators)

        # Extract risk management
        risk_mgmt = self._extract_risk_management(text_lower)

        # Extract strategy name
        name = self._extract_name(text)

        ir = StrategyIR(
            name=name,
            description=text[:500],
            type=strategy_type,
            instruments=instruments if instruments else ["EURUSD"],
            timeframes=timeframes if timeframes else [Timeframe.H1],
            indicators=indicators,
            entry_signals=entry_signals,
            exit_signals=exit_signals,
            risk_management=risk_mgmt,
            source_idea=text[:1000],
        )

        return ir

    def _extract_strategy_type(self, text: str) -> StrategyType:
        for keyword, stype in STRATEGY_TYPE_KEYWORDS.items():
            if keyword in text:
                return stype
        return StrategyType.CUSTOM

    def _extract_instruments(self, text: str) -> List[str]:
        """Extract trading instruments/symbols."""
        instruments = []
        # Common forex pairs
        forex_pattern = r'\b(EURUSD|GBPUSD|USDJPY|USDCHF|AUDUSD|USDCAD|NZDUSD|EURGBP|EURJPY|GBPJPY|XAUUSD|XAGUSD|BTCUSD|ETHUSD|SPY|QQQ|AAPL|MSFT|GOOGL|TSLA|AMZN|NVDA|EUR/USD|GBP/USD|USD/JPY|gold|silver|bitcoin)\b'
        matches = re.findall(forex_pattern, text, re.IGNORECASE)
        if matches:
            instruments = [m.replace("/", "").upper() for m in matches]

        # Map common names
        name_map = {"GOLD": "XAUUSD", "SILVER": "XAGUSD", "BITCOIN": "BTCUSD"}
        instruments = [name_map.get(i, i) for i in instruments]

        return list(set(instruments))

    def _extract_timeframes(self, text: str) -> List[Timeframe]:
        timeframes = []
        for keyword, tf in TIMEFRAME_KEYWORDS.items():
            if keyword in text:
                timeframes.append(tf)
        return list(set(timeframes))

    def _extract_indicators(self, text: str) -> List[Indicator]:
        indicators = []
        found_types = set()

        for keyword, ind_type in INDICATOR_KEYWORDS.items():
            if keyword in text and ind_type not in found_types:
                found_types.add(ind_type)
                params = self._extract_indicator_params(text, ind_type)
                indicators.append(Indicator(type=ind_type, parameters=params))

        return indicators

    def _extract_indicator_params(self, text: str, ind_type: IndicatorType) -> Dict[str, Any]:
        """Extract parameters for a specific indicator from text."""
        params = {}

        # Look for period values near the indicator mention
        period_patterns = [
            rf'{ind_type.value}\s*\(?\s*(\d+)\)?',
            rf'(\d+)\s*{ind_type.value}',
            rf'{ind_type.value}\s+de\s+(\d+)',
            rf'{ind_type.value}\s+period\s+(\d+)',
            rf'{ind_type.value}\s+período\s+(\d+)',
        ]

        for pattern in period_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                params["period"] = int(match.group(1))
                break

        # Default periods
        if "period" not in params:
            defaults = {
                IndicatorType.SMA: 20, IndicatorType.EMA: 20, IndicatorType.WMA: 20,
                IndicatorType.RSI: 14, IndicatorType.MACD: None,
                IndicatorType.BOLLINGER_BANDS: 20, IndicatorType.ATR: 14,
                IndicatorType.STOCHASTIC: 14, IndicatorType.CCI: 20,
                IndicatorType.ADX: 14, IndicatorType.MFI: 14,
            }
            if ind_type in defaults and defaults[ind_type]:
                params["period"] = defaults[ind_type]

        # Bollinger Bands std dev
        if ind_type == IndicatorType.BOLLINGER_BANDS:
            std_match = re.search(r'(?:std|dev|desviación)\s*\(?\s*(\d+(?:\.\d+)?)\)?', text, re.IGNORECASE)
            if std_match:
                params["std_dev"] = float(std_match.group(1))
            elif "std_dev" not in params:
                params["std_dev"] = 2.0

        # RSI levels
        if ind_type == IndicatorType.RSI:
            ob_match = re.search(r'(?:overbought|sobrecompra)\s*\(?\s*(\d+)\)?', text, re.IGNORECASE)
            os_match = re.search(r'(?:oversold|sobreventa)\s*\(?\s*(\d+)\)?', text, re.IGNORECASE)
            if ob_match:
                params["overbought"] = int(ob_match.group(1))
            if os_match:
                params["oversold"] = int(os_match.group(1))

        # MACD parameters
        if ind_type == IndicatorType.MACD:
            params.setdefault("fast_period", 12)
            params.setdefault("slow_period", 26)
            params.setdefault("signal_period", 9)

        return params

    def _extract_entry_signals(self, text: str, indicators: List[Indicator]) -> List[Signal]:
        """Extract entry signal conditions from text."""
        signals = []
        text_lower = text.lower()

        # Buy signals
        buy_keywords = ["buy", "long", "enter long", "go long", "abrir compra", "comprar", "entrada en compra"]
        sell_keywords = ["sell", "short", "enter short", "go short", "abrir venta", "vender", "entrada en venta"]

        has_buy = any(kw in text_lower for kw in buy_keywords)
        has_sell = any(kw in text_lower for kw in sell_keywords)

        if has_buy or (not has_buy and not has_sell):
            # Default: create a buy signal based on indicators
            conditions = self._build_conditions_from_indicators(text_lower, indicators, "buy")
            if conditions:
                signals.append(Signal(
                    type=SignalType.BUY,
                    condition=ConditionGroup(logic="AND", conditions=conditions),
                    confidence=0.8
                ))

        if has_sell:
            conditions = self._build_conditions_from_indicators(text_lower, indicators, "sell")
            if conditions:
                signals.append(Signal(
                    type=SignalType.SELL,
                    condition=ConditionGroup(logic="AND", conditions=conditions),
                    confidence=0.8
                ))

        # If no signals could be extracted, create a default one
        if not signals and indicators:
            ind = indicators[0]
            if ind.type in (IndicatorType.SMA, IndicatorType.EMA):
                signals.append(Signal(
                    type=SignalType.BUY,
                    condition=ConditionGroup(logic="AND", conditions=[
                        Condition(left_operand="close", operator=ConditionOperator.CROSSES_ABOVE,
                                  right_operand=f"{ind.type.value}({ind.parameters.get('period', 20)})")
                    ]),
                    confidence=0.6
                ))
            elif ind.type == IndicatorType.RSI:
                signals.append(Signal(
                    type=SignalType.BUY,
                    condition=ConditionGroup(logic="AND", conditions=[
                        Condition(left_operand=f"rsi({ind.parameters.get('period', 14)})",
                                  operator=ConditionOperator.LESS_THAN,
                                  right_operand=str(ind.parameters.get("oversold", 30)))
                    ]),
                    confidence=0.6
                ))

        return signals

    def _extract_exit_signals(self, text: str, indicators: List[Indicator]) -> List[Signal]:
        """Extract exit signal conditions from text."""
        signals = []
        text_lower = text.lower()

        # Look for explicit exit conditions
        exit_keywords = ["exit", "close", "salida", "cerrar"]
        if any(kw in text_lower for kw in exit_keywords):
            conditions = self._build_conditions_from_indicators(text_lower, indicators, "exit")
            if conditions:
                signals.append(Signal(
                    type=SignalType.CLOSE_ALL,
                    condition=ConditionGroup(logic="OR", conditions=conditions),
                    confidence=0.7
                ))

        return signals

    def _build_conditions_from_indicators(self, text: str, indicators: List[Indicator],
                                           direction: str) -> List[Condition]:
        """Build condition objects from extracted indicators and text context."""
        conditions = []

        for ind in indicators:
            period = ind.parameters.get("period", 20)

            if ind.type in (IndicatorType.SMA, IndicatorType.EMA, IndicatorType.WMA):
                if direction == "buy":
                    conditions.append(Condition(
                        left_operand="close",
                        operator=ConditionOperator.CROSSES_ABOVE,
                        right_operand=f"{ind.type.value}({period})"
                    ))
                elif direction == "sell":
                    conditions.append(Condition(
                        left_operand="close",
                        operator=ConditionOperator.CROSSES_BELOW,
                        right_operand=f"{ind.type.value}({period})"
                    ))

            elif ind.type == IndicatorType.RSI:
                if direction == "buy":
                    conditions.append(Condition(
                        left_operand=f"rsi({period})",
                        operator=ConditionOperator.LESS_THAN,
                        right_operand=str(ind.parameters.get("oversold", 30))
                    ))
                elif direction == "sell":
                    conditions.append(Condition(
                        left_operand=f"rsi({period})",
                        operator=ConditionOperator.GREATER_THAN,
                        right_operand=str(ind.parameters.get("overbought", 70))
                    ))

            elif ind.type == IndicatorType.MACD:
                if direction == "buy":
                    conditions.append(Condition(
                        left_operand="macd_line",
                        operator=ConditionOperator.CROSSES_ABOVE,
                        right_operand="macd_signal"
                    ))
                elif direction == "sell":
                    conditions.append(Condition(
                        left_operand="macd_line",
                        operator=ConditionOperator.CROSSES_BELOW,
                        right_operand="macd_signal"
                    ))

            elif ind.type == IndicatorType.BOLLINGER_BANDS:
                if direction == "buy":
                    conditions.append(Condition(
                        left_operand="close",
                        operator=ConditionOperator.LESS_THAN,
                        right_operand="lower_bb"
                    ))
                elif direction == "sell":
                    conditions.append(Condition(
                        left_operand="close",
                        operator=ConditionOperator.GREATER_THAN,
                        right_operand="upper_bb"
                    ))

        return conditions

    def _extract_risk_management(self, text: str) -> RiskManagement:
        """Extract risk management parameters from text."""
        rm = RiskManagement()

        # Stop loss
        sl_match = re.search(
            r'(?:stop\s*loss|stop|sl|stop\s*loss\s+de)\s*(?:of|de|:)?\s*\(?\s*(\d+(?:\.\d+)?)\s*(?:pips|pip|points|point|puntos)?\)?',
            text, re.IGNORECASE
        )
        if sl_match:
            rm.stop_loss = float(sl_match.group(1))
            rm.stop_loss_type = "fixed"

        # ATR-based stop loss
        atr_sl = re.search(
            r'(?:atr|average true range)\s+(?:stop|sl)\s*\(?\s*(\d+(?:\.\d+)?)\s*(?:x|times|veces)?\)?',
            text, re.IGNORECASE
        )
        if atr_sl:
            rm.stop_loss = float(atr_sl.group(1))
            rm.stop_loss_type = "atr_based"

        # Take profit
        tp_match = re.search(
            r'(?:take\s*profit|tp|take\s*profit\s+de|objetivo)\s*(?:of|de|:)?\s*\(?\s*(\d+(?:\.\d+)?)\s*(?:pips|pip|points|point|puntos)?\)?',
            text, re.IGNORECASE
        )
        if tp_match:
            rm.take_profit = float(tp_match.group(1))
            rm.take_profit_type = "fixed"

        # Risk per trade
        risk_match = re.search(
            r'(?:risk|riesgo)\s*(?:per trade|por operación)?\s*\(?\s*(\d+(?:\.\d+)?)\s*%?\)?',
            text, re.IGNORECASE
        )
        if risk_match:
            rm.risk_per_trade = float(risk_match.group(1))

        # Position size
        pos_match = re.search(
            r'(?:position size|tamaño|lot|lots|lotes)\s*\(?\s*(\d+(?:\.\d+)?)\s*(?:lots|lotes)?\)?',
            text, re.IGNORECASE
        )
        if pos_match:
            rm.max_position_size = float(pos_match.group(1))

        # Max drawdown
        dd_match = re.search(
            r'(?:max drawdown|máximo drawdown|drawdown)\s*\(?\s*(\d+(?:\.\d+)?)\s*%?\)?',
            text, re.IGNORECASE
        )
        if dd_match:
            rm.max_drawdown_limit = float(dd_match.group(1))

        # Trailing stop
        ts_match = re.search(
            r'(?:trailing stop|trailing)\s*\(?\s*(\d+(?:\.\d+)?)\s*(?:pips|pip|points|puntos)?\)?',
            text, re.IGNORECASE
        )
        if ts_match:
            rm.trailing_stop = float(ts_match.group(1))

        return rm

    def _extract_name(self, text: str) -> str:
        """Try to extract a strategy name from the text."""
        name_match = re.search(
            r'(?:strategy|estrategia|strategy name|nombre)\s*(?:is|es|:)?\s*["\']?([^"\'\n.]+)["\']?',
            text, re.IGNORECASE
        )
        if name_match:
            return name_match.group(1).strip()[:50]
        # Use first few words
        words = text.split()[:5]
        return " ".join(words)[:50]

    def to_json(self, ir: StrategyIR) -> str:
        return ir.model_dump_json(indent=2)

    def from_json(self, json_str: str) -> StrategyIR:
        data = json.loads(json_str)
        return StrategyIR.from_dict(data)
