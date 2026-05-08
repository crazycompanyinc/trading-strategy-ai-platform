"""
Strategy Parser - Converts natural language + images into Strategy IR.
Supports both classical indicators AND ICT concepts (FVG, Order Block, BOS, CHoCH, etc.)
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


# ─── Classical indicator keywords ──────────────────────────────────────────────

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

# ─── ICT concept keywords ──────────────────────────────────────────────────────
# These map to special indicator types that the backtester understands

ICT_CONCEPTS = {
    # Fair Value Gap
    "fvg": "ict_fvg",
    "fair value gap": "ict_fvg",
    "fair value": "ict_fvg",
    "fvg alcista": "ict_fvg_bullish",
    "fvg bajista": "ict_fvg_bearish",
    "bullish fvg": "ict_fvg_bullish",
    "bearish fvg": "ict_fvg_bearish",
    "primer fvg": "ict_fvg_first",
    "first fvg": "ict_fvg_first",
    "ffvg": "ict_fvg_first",
    
    # Order Block
    "order block": "ict_order_block",
    "orderblock": "ict_order_block",
    "ob": "ict_order_block",
    "bloque de ordenes": "ict_order_block",
    "bloque de orden": "ict_order_block",
    "bullish order block": "ict_order_block_bullish",
    "bearish order block": "ict_order_block_bearish",
    "order block alcista": "ict_order_block_bullish",
    "order block bajista": "ict_order_block_bearish",
    
    # Break of Structure
    "bos": "ict_bos",
    "break of structure": "ict_bos",
    "ruptura de estructura": "ict_bos",
    "break structure": "ict_bos",
    
    # Change of Character
    "choch": "ict_choch",
    "change of character": "ict_choch",
    "cambio de caracter": "ict_choch",
    
    # Liquidity
    "liquidity": "ict_liquidity",
    "liquidez": "ict_liquidity",
    "sweep": "ict_liquidity_sweep",
    "sweep de liquidez": "ict_liquidity_sweep",
    "liquidity sweep": "ict_liquidity_sweep",
    
    # Premium / Discount
    "premium": "ict_premium",
    "discount": "ict_discount",
    "zona premium": "ict_premium",
    "zona discount": "ict_discount",
    
    # Optimal Trade Entry
    "ote": "ict_ote",
    "optimal trade entry": "ict_ote",
    
    # Killzones
    "killzone": "ict_killzone",
    "kill zone": "ict_killzone",
    "zona de liquidacion": "ict_killzone",
    "london killzone": "ict_killzone_london",
    "new york killzone": "ict_killzone_ny",
    "asian killzone": "ict_killzone_asian",
    
    # Consequent Encroachment
    "consequent encroachment": "ict_ce",
    "ce": "ict_ce",
    "consequent encroachment": "ict_ce",
}

STRATEGY_TYPE_KEYWORDS = {
    "trend following": StrategyType.TREND_FOLLOWING, "trend": StrategyType.TREND_FOLLOWING,
    "seguir tendencia": StrategyType.TREND_FOLLOWING, "seguimiento de tendencia": StrategyType.TREND_FOLLOWING,
    "mean reversion": StrategyType.MEAN_REVERSION, "reversion": StrategyType.MEAN_REVERSION, "reversión": StrategyType.MEAN_REVERSION,
    "breakout": StrategyType.BREAKOUT, "ruptura": StrategyType.BREAKOUT,
    "scalping": StrategyType.SCALPING, "scalp": StrategyType.SCALPING,
    "swing": StrategyType.SWING, "swing trading": StrategyType.SWING,
    "ict": StrategyType.CUSTOM, "inner circle trader": StrategyType.CUSTOM,
    "smart money": StrategyType.CUSTOM, "smart money concepts": StrategyType.CUSTOM,
    "smc": StrategyType.CUSTOM,
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
    Supports classical indicators AND ICT/Smart Money concepts.
    """

    def parse(self, text: str, images: Optional[List[str]] = None) -> StrategyIR:
        text_lower = text.lower()

        strategy_type = self._extract_strategy_type(text_lower)
        instruments = self._extract_instruments(text)
        timeframes = self._extract_timeframes(text_lower)
        
        # Extract both classical indicators AND ICT concepts
        indicators = self._extract_indicators(text_lower)
        ict_concepts = self._extract_ict_concepts(text_lower)
        
        # Merge: ICT concepts become special indicators
        all_indicators = indicators + ict_concepts
        
        entry_signals = self._extract_entry_signals(text_lower, all_indicators)
        exit_signals = self._extract_exit_signals(text_lower, all_indicators)
        risk_mgmt = self._extract_risk_management(text_lower)
        name = self._extract_name(text)

        # If no exit signals from explicit keywords, generate defaults
        if not exit_signals and entry_signals:
            has_buy = any(s.type == SignalType.BUY for s in entry_signals)
            has_sell = any(s.type == SignalType.SELL for s in entry_signals)
            if has_buy:
                exit_signals.append(Signal(
                    type=SignalType.CLOSE_LONG,
                    condition=ConditionGroup(logic="AND", conditions=[
                        Condition(left_operand="position_bars_held",
                                  operator=ConditionOperator.GREATER_THAN,
                                  right_operand="10")
                    ]),
                    confidence=0.5,
                ))
            if has_sell:
                exit_signals.append(Signal(
                    type=SignalType.CLOSE_SHORT,
                    condition=ConditionGroup(logic="AND", conditions=[
                        Condition(left_operand="position_bars_held",
                                  operator=ConditionOperator.GREATER_THAN,
                                  right_operand="10")
                    ]),
                    confidence=0.5,
                ))

        # If we detected ICT concepts but no explicit strategy type, mark as ICT
        if ict_concepts and strategy_type == StrategyType.CUSTOM:
            strategy_type = StrategyType.CUSTOM  # Keep as CUSTOM but with ICT tags

        ir = StrategyIR(
            name=name,
            description=text[:500],
            type=strategy_type,
            instruments=instruments if instruments else ["EURUSD"],
            timeframes=timeframes if timeframes else [Timeframe.H1],
            indicators=all_indicators,
            entry_signals=entry_signals,
            exit_signals=exit_signals,
            risk_management=risk_mgmt,
            source_idea=text[:1000],
            tags=self._extract_tags(text_lower, ict_concepts),
        )

        return ir

    def _extract_tags(self, text: str, ict_concepts: List[Indicator]) -> List[str]:
        tags = []
        for concept in ict_concepts:
            tags.append(concept.type.value)
        if "ict" in text or "inner circle" in text or "smart money" in text or "smc" in text:
            tags.append("ict")
        return list(set(tags))

    def _extract_strategy_type(self, text: str) -> StrategyType:
        for keyword, stype in STRATEGY_TYPE_KEYWORDS.items():
            if keyword in text:
                return stype
        return StrategyType.CUSTOM

    def _extract_instruments(self, text: str) -> List[str]:
        instruments = []
        forex_pattern = r'\b(EURUSD|GBPUSD|USDJPY|USDCHF|AUDUSD|USDCAD|NZDUSD|EURGBP|EURJPY|GBPJPY|XAUUSD|XAGUSD|BTCUSD|ETHUSD|SPY|QQQ|AAPL|MSFT|GOOGL|TSLA|AMZN|NVDA|EUR/USD|GBP/USD|USD/JPY|gold|silver|bitcoin)\b'
        matches = re.findall(forex_pattern, text, re.IGNORECASE)
        if matches:
            instruments = [m.replace("/", "").upper() for m in matches]
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
        """Extract classical technical indicators."""
        indicators = []
        found_types = set()

        for keyword, ind_type in INDICATOR_KEYWORDS.items():
            if keyword in text and ind_type not in found_types:
                found_types.add(ind_type)
                params = self._extract_indicator_params(text, ind_type)
                indicators.append(Indicator(type=ind_type, parameters=params))

        return indicators

    def _extract_ict_concepts(self, text: str) -> List[Indicator]:
        """Extract ICT/Smart Money concepts and convert them to indicators."""
        concepts = []
        found_types = set()

        # Sort by length (longest first) to match "fair value gap" before "fvg"
        sorted_concepts = sorted(ICT_CONCEPTS.items(), key=lambda x: len(x[0]), reverse=True)

        for keyword, concept_type in sorted_concepts:
            if keyword in text and concept_type not in found_types:
                found_types.add(concept_type)
                params = self._extract_ict_params(text, concept_type)
                concepts.append(Indicator(
                    type=IndicatorType.CUSTOM,
                    parameters={"ict_concept": concept_type, **params},
                ))

        return concepts

    def _extract_ict_params(self, text: str, concept_type: str) -> Dict[str, Any]:
        """Extract parameters for ICT concepts."""
        params = {}

        if "fvg" in concept_type:
            params["lookback"] = 50  # bars to look back for FVG detection
            params["min_gap_pips"] = 1.0  # minimum gap size in pips
            params["fill_threshold"] = 0.5  # how much of gap must be filled to trigger
            # Check for specific FVG types
            if "bullish" in concept_type or "alcista" in text:
                params["direction"] = "bullish"
            elif "bearish" in concept_type or "bajista" in text:
                params["direction"] = "bearish"
            else:
                params["direction"] = "both"
            if "first" in concept_type or "primer" in text:
                params["mode"] = "first_only"
            else:
                params["mode"] = "all"

        elif "order_block" in concept_type:
            params["lookback"] = 100
            params["min_ob_size_pips"] = 5.0
            if "bullish" in concept_type or "alcista" in text:
                params["direction"] = "bullish"
            elif "bearish" in concept_type or "bajista" in text:
                params["direction"] = "bearish"
            else:
                params["direction"] = "both"

        elif "bos" in concept_type:
            params["lookback"] = 50
            params["swing_detection_bars"] = 5

        elif "choch" in concept_type:
            params["lookback"] = 50
            params["swing_detection_bars"] = 5

        elif "liquidity" in concept_type:
            params["lookback"] = 100
            params["sweep_threshold_bars"] = 3

        elif "killzone" in concept_type:
            if "london" in concept_type:
                params["start_hour"] = 7
                params["end_hour"] = 10
            elif "ny" in concept_type:
                params["start_hour"] = 12
                params["end_hour"] = 15
            elif "asian" in concept_type:
                params["start_hour"] = 0
                params["end_hour"] = 3
            else:
                params["start_hour"] = 7
                params["end_hour"] = 15

        return params

    def _extract_indicator_params(self, text: str, ind_type: IndicatorType) -> Dict[str, Any]:
        params = {}
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
        if ind_type == IndicatorType.BOLLINGER_BANDS:
            std_match = re.search(r'(?:std|dev|desviación)\s*\(?\s*(\d+(?:\.\d+)?)\)?', text, re.IGNORECASE)
            if std_match:
                params["std_dev"] = float(std_match.group(1))
            elif "std_dev" not in params:
                params["std_dev"] = 2.0
        if ind_type == IndicatorType.RSI:
            ob_match = re.search(r'(?:overbought|sobrecompra)\s*\(?\s*(\d+)\)?', text, re.IGNORECASE)
            os_match = re.search(r'(?:oversold|sobreventa)\s*\(?\s*(\d+)\)?', text, re.IGNORECASE)
            if ob_match:
                params["overbought"] = int(ob_match.group(1))
            if os_match:
                params["oversold"] = int(os_match.group(1))
        if ind_type == IndicatorType.MACD:
            params.setdefault("fast_period", 12)
            params.setdefault("slow_period", 26)
            params.setdefault("signal_period", 9)
        return params

    def _extract_entry_signals(self, text: str, indicators: List[Indicator]) -> List[Signal]:
        signals = []
        text_lower = text.lower()

        buy_keywords = ["buy", "long", "enter long", "go long", "abrir compra", "comprar", "entrada en compra", "entrar en compra"]
        sell_keywords = ["sell", "short", "enter short", "go short", "abrir venta", "vender", "entrada en venta", "entrar en venta"]

        has_buy = any(kw in text_lower for kw in buy_keywords)
        has_sell = any(kw in text_lower for kw in sell_keywords)

        # Check for ICT-specific entry logic
        ict_indicators = [ind for ind in indicators if ind.type == IndicatorType.CUSTOM and "ict_concept" in ind.parameters]
        classical_indicators = [ind for ind in indicators if ind.type != IndicatorType.CUSTOM or "ict_concept" not in ind.parameters]

        if ict_indicators:
            # Build ICT-based entry signals — deduplicate by (concept_type, direction)
            seen = set()
            for ict in ict_indicators:
                concept = ict.parameters.get("ict_concept", "")
                direction = ict.parameters.get("direction", "both")

                if "fvg" in concept:
                    if direction in ("bullish", "both") and ("fvg", "buy") not in seen:
                        seen.add(("fvg", "buy"))
                        signals.append(Signal(
                            type=SignalType.BUY,
                            condition=ConditionGroup(logic="AND", conditions=[
                                Condition(
                                    left_operand="fvg_bullish",
                                    operator=ConditionOperator.EQUAL,
                                    right_operand="true",
                                )
                            ]),
                            confidence=0.75,
                        ))
                    if direction in ("bearish", "both") and ("fvg", "sell") not in seen:
                        seen.add(("fvg", "sell"))
                        signals.append(Signal(
                            type=SignalType.SELL,
                            condition=ConditionGroup(logic="AND", conditions=[
                                Condition(
                                    left_operand="fvg_bearish",
                                    operator=ConditionOperator.EQUAL,
                                    right_operand="true",
                                )
                            ]),
                            confidence=0.75,
                        ))

                elif "order_block" in concept:
                    if direction in ("bullish", "both") and ("ob", "buy") not in seen:
                        seen.add(("ob", "buy"))
                        signals.append(Signal(
                            type=SignalType.BUY,
                            condition=ConditionGroup(logic="AND", conditions=[
                                Condition(
                                    left_operand="price_at_ob_bullish",
                                    operator=ConditionOperator.EQUAL,
                                    right_operand="true",
                                )
                            ]),
                            confidence=0.7,
                        ))
                    if direction in ("bearish", "both") and ("ob", "sell") not in seen:
                        seen.add(("ob", "sell"))
                        signals.append(Signal(
                            type=SignalType.SELL,
                            condition=ConditionGroup(logic="AND", conditions=[
                                Condition(
                                    left_operand="price_at_ob_bearish",
                                    operator=ConditionOperator.EQUAL,
                                    right_operand="true",
                                )
                            ]),
                            confidence=0.7,
                        ))

                elif "bos" in concept and "bos" not in seen:
                    seen.add("bos")
                    signals.append(Signal(
                        type=SignalType.BUY,
                        condition=ConditionGroup(logic="AND", conditions=[
                            Condition(
                                left_operand="bos_bullish",
                                operator=ConditionOperator.EQUAL,
                                right_operand="true",
                            )
                        ]),
                        confidence=0.65,
                    ))
                    signals.append(Signal(
                        type=SignalType.SELL,
                        condition=ConditionGroup(logic="AND", conditions=[
                            Condition(
                                left_operand="bos_bearish",
                                operator=ConditionOperator.EQUAL,
                                right_operand="true",
                            )
                        ]),
                        confidence=0.65,
                    ))

                elif "choch" in concept and "choch" not in seen:
                    seen.add("choch")
                    signals.append(Signal(
                        type=SignalType.BUY,
                        condition=ConditionGroup(logic="AND", conditions=[
                            Condition(
                                left_operand="choch_bullish",
                                operator=ConditionOperator.EQUAL,
                                right_operand="true",
                            )
                        ]),
                        confidence=0.65,
                    ))
                    signals.append(Signal(
                        type=SignalType.SELL,
                        condition=ConditionGroup(logic="AND", conditions=[
                            Condition(
                                left_operand="choch_bearish",
                                operator=ConditionOperator.EQUAL,
                                right_operand="true",
                            )
                        ]),
                        confidence=0.65,
                    ))

        # Classical indicator signals
        if classical_indicators and not ict_indicators:
            if has_buy or (not has_buy and not has_sell):
                conditions = self._build_conditions_from_indicators(text_lower, classical_indicators, "buy")
                if conditions:
                    signals.append(Signal(
                        type=SignalType.BUY,
                        condition=ConditionGroup(logic="AND", conditions=conditions),
                        confidence=0.8,
                    ))

            if has_sell:
                conditions = self._build_conditions_from_indicators(text_lower, classical_indicators, "sell")
                if conditions:
                    signals.append(Signal(
                        type=SignalType.SELL,
                        condition=ConditionGroup(logic="AND", conditions=conditions),
                        confidence=0.8,
                    ))

        # Fallback: if no signals at all but we have indicators, create default
        if not signals:
            if ict_indicators:
                # Default ICT signal: buy at first bullish FVG
                signals.append(Signal(
                    type=SignalType.BUY,
                    condition=ConditionGroup(logic="AND", conditions=[
                        Condition(
                            left_operand="fvg_bullish",
                            operator=ConditionOperator.EQUAL,
                            right_operand="true",
                        )
                    ]),
                    confidence=0.6,
                ))
            elif classical_indicators:
                ind = classical_indicators[0]
                if ind.type in (IndicatorType.SMA, IndicatorType.EMA):
                    period = ind.parameters.get("period", 20)
                    signals.append(Signal(
                        type=SignalType.BUY,
                        condition=ConditionGroup(logic="AND", conditions=[
                            Condition(left_operand="close", operator=ConditionOperator.CROSSES_ABOVE,
                                      right_operand=f"{ind.type.value}({period})")
                        ]),
                        confidence=0.6,
                    ))
                elif ind.type == IndicatorType.RSI:
                    period = ind.parameters.get("period", 14)
                    oversold = ind.parameters.get("oversold", 30)
                    signals.append(Signal(
                        type=SignalType.BUY,
                        condition=ConditionGroup(logic="AND", conditions=[
                            Condition(left_operand=f"rsi({period})",
                                      operator=ConditionOperator.LESS_THAN,
                                      right_operand=str(oversold))
                        ]),
                        confidence=0.6,
                    ))

        # ── Always ensure we have exit signals ───────────────────────────
        # (This is a local helper — actual exit signals set in parse())
        _default_exits = []
        if signals:
            has_buy = any(s.type == SignalType.BUY for s in signals)
            has_sell = any(s.type == SignalType.SELL for s in signals)
            if has_buy:
                _default_exits.append(Signal(
                    type=SignalType.CLOSE_LONG,
                    condition=ConditionGroup(logic="AND", conditions=[
                        Condition(left_operand="position_bars_held",
                                  operator=ConditionOperator.GREATER_THAN,
                                  right_operand="10")
                    ]),
                    confidence=0.5,
                ))
            if has_sell:
                _default_exits.append(Signal(
                    type=SignalType.CLOSE_SHORT,
                    condition=ConditionGroup(logic="AND", conditions=[
                        Condition(left_operand="position_bars_held",
                                  operator=ConditionOperator.GREATER_THAN,
                                  right_operand="10")
                    ]),
                    confidence=0.5,
                ))

        return signals

    def _extract_exit_signals(self, text: str, indicators: List[Indicator]) -> List[Signal]:
        """Extract exit signals. Returns signals only if explicit exit keywords found."""
        signals = []
        exit_keywords = ["exit", "close", "salida", "cerrar"]
        if any(kw in text for kw in exit_keywords):
            conditions = self._build_conditions_from_indicators(text, indicators, "exit")
            if conditions:
                signals.append(Signal(
                    type=SignalType.CLOSE_ALL,
                    condition=ConditionGroup(logic="OR", conditions=conditions),
                    confidence=0.7,
                ))
        return signals

    def _build_conditions_from_indicators(self, text: str, indicators: List[Indicator],
                                           direction: str) -> List[Condition]:
        conditions = []
        for ind in indicators:
            # Skip ICT custom indicators here
            if ind.type == IndicatorType.CUSTOM and "ict_concept" in ind.parameters:
                continue
            period = ind.parameters.get("period", 20)
            if ind.type in (IndicatorType.SMA, IndicatorType.EMA, IndicatorType.WMA):
                if direction == "buy":
                    conditions.append(Condition(
                        left_operand="close", operator=ConditionOperator.CROSSES_ABOVE,
                        right_operand=f"{ind.type.value}({period})"
                    ))
                elif direction == "sell":
                    conditions.append(Condition(
                        left_operand="close", operator=ConditionOperator.CROSSES_BELOW,
                        right_operand=f"{ind.type.value}({period})"
                    ))
            elif ind.type == IndicatorType.RSI:
                if direction == "buy":
                    conditions.append(Condition(
                        left_operand=f"rsi({period})", operator=ConditionOperator.LESS_THAN,
                        right_operand=str(ind.parameters.get("oversold", 30))
                    ))
                elif direction == "sell":
                    conditions.append(Condition(
                        left_operand=f"rsi({period})", operator=ConditionOperator.GREATER_THAN,
                        right_operand=str(ind.parameters.get("overbought", 70))
                    ))
            elif ind.type == IndicatorType.MACD:
                if direction == "buy":
                    conditions.append(Condition(
                        left_operand="macd_line", operator=ConditionOperator.CROSSES_ABOVE,
                        right_operand="macd_signal"
                    ))
                elif direction == "sell":
                    conditions.append(Condition(
                        left_operand="macd_line", operator=ConditionOperator.CROSSES_BELOW,
                        right_operand="macd_signal"
                    ))
            elif ind.type == IndicatorType.BOLLINGER_BANDS:
                if direction == "buy":
                    conditions.append(Condition(
                        left_operand="close", operator=ConditionOperator.LESS_THAN,
                        right_operand="lower_bb"
                    ))
                elif direction == "sell":
                    conditions.append(Condition(
                        left_operand="close", operator=ConditionOperator.GREATER_THAN,
                        right_operand="upper_bb"
                    ))
        return conditions

    def _extract_risk_management(self, text: str) -> RiskManagement:
        rm = RiskManagement()
        sl_match = re.search(
            r'(?:stop\s*loss|stop|sl|stop\s*loss\s+de)\s*(?:of|de|:)?\s*\(?\s*(\d+(?:\.\d+)?)\s*(?:pips|pip|points|point|puntos)?\)?',
            text, re.IGNORECASE
        )
        if sl_match:
            rm.stop_loss = float(sl_match.group(1))
            rm.stop_loss_type = "fixed"
        atr_sl = re.search(
            r'(?:atr|average true range)\s+(?:stop|sl)\s*\(?\s*(\d+(?:\.\d+)?)\s*(?:x|times|veces)?\)?',
            text, re.IGNORECASE
        )
        if atr_sl:
            rm.stop_loss = float(atr_sl.group(1))
            rm.stop_loss_type = "atr_based"
        tp_match = re.search(
            r'(?:take\s*profit|tp|take\s*profit\s+de|objetivo)\s*(?:of|de|:)?\s*\(?\s*(\d+(?:\.\d+)?)\s*(?:pips|pip|points|point|puntos)?\)?',
            text, re.IGNORECASE
        )
        if tp_match:
            rm.take_profit = float(tp_match.group(1))
            rm.take_profit_type = "fixed"
        risk_match = re.search(
            r'(?:risk|riesgo)\s*(?:per trade|por operación)?\s*\(?\s*(\d+(?:\.\d+)?)\s*%?\)?',
            text, re.IGNORECASE
        )
        if risk_match:
            rm.risk_per_trade = float(risk_match.group(1))
        pos_match = re.search(
            r'(?:position size|tamaño|lot|lots|lotes)\s*\(?\s*(\d+(?:\.\d+)?)\s*(?:lots|lotes)?\)?',
            text, re.IGNORECASE
        )
        if pos_match:
            rm.max_position_size = float(pos_match.group(1))
        dd_match = re.search(
            r'(?:max drawdown|máximo drawdown|drawdown)\s*\(?\s*(\d+(?:\.\d+)?)\s*%?\)?',
            text, re.IGNORECASE
        )
        if dd_match:
            rm.max_drawdown_limit = float(dd_match.group(1))
        ts_match = re.search(
            r'(?:trailing stop|trailing)\s*\(?\s*(\d+(?:\.\d+)?)\s*(?:pips|pip|points|puntos)?\)?',
            text, re.IGNORECASE
        )
        if ts_match:
            rm.trailing_stop = float(ts_match.group(1))
        return rm

    def _extract_name(self, text: str) -> str:
        name_match = re.search(
            r'(?:strategy|estrategia|strategy name|nombre)\s*(?:is|es|:)?\s*["\']?([^"\'\n.]+)["\']?',
            text, re.IGNORECASE
        )
        if name_match:
            return name_match.group(1).strip()[:50]
        words = text.split()[:5]
        return " ".join(words)[:50]

    def to_json(self, ir: StrategyIR) -> str:
        return ir.model_dump_json(indent=2)

    def from_json(self, json_str: str) -> StrategyIR:
        data = json.loads(json_str)
        return StrategyIR.from_dict(data)
