"""
Smart Money Trap Strategy Generator & Backtests multiple ICT-based trap strategy variations,
finds the best performing one without overfitting, and generates MT5 code.
"""
import json
import math
import random
import copy
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple, Optional

import numpy as np

# ── Synthetic Data Generation ──────────────────────────────────────────────

def generate_synthetic_data(symbol: str, start_date: str, end_date: str, n_bars: int = 8000) -> List[Dict]:
    random.seed(42)
    np.random.seed(42)
    initial_prices = {
        "EURUSD": 1.1000, "GBPUSD": 1.2500, "USDJPY": 135.0,
        "XAUUSD": 1900.0, "XAGUSD": 23.0, "BTCUSD": 30000.0
    }
    price = initial_prices.get(symbol, 1.0)
    volatilities = {
        "EURUSD": 0.0008, "GBPUSD": 0.001, "USDJPY": 0.0008,
        "XAUUSD": 0.01, "XAGUSD": 0.015, "BTCUSD": 0.03
    }
    vol = volatilities.get(symbol, 0.001)
    drift = 0.00002
    dt = 1.0
    start = datetime.strptime(start_date, "%Y-%m-%d")
    data = []
    for i in range(n_bars):
        date = start + timedelta(hours=i)
        shock = np.random.normal(0, 1)
        ret = drift * dt + vol * math.sqrt(dt) * shock
        open_p = price
        close_p = price * (1 + ret)
        high_p = max(open_p, close_p) * (1 + abs(np.random.normal(0, vol * 0.5)))
        low_p = min(open_p, close_p) * (1 - abs(np.random.normal(0, vol * 0.5)))
        volume = int(np.random.lognormal(10, 1))
        data.append({
            "date": date,
            "open": round(open_p, 6),
            "high": round(high_p, 6),
            "low": round(low_p, 6),
            "close": round(close_p, 6),
            "volume": volume
        })
        price = close_p
    return data


# ── Indicator Calculations ─────────────────────────────────────────────────

def calc_ema(data: List[dict], period: int) -> List[dict]:
    closes = [d["close"] for d in data]
    mult = 2.0 / (period + 1)
    ema = closes[0]
    for i in range(len(data)):
        if i > 0:
            ema = (closes[i] - ema) * mult + ema
        data[i][f"ema({period})"] = round(ema, 6)
    return data

def calc_sma(data: List[dict], period: int) -> List[dict]:
    closes = [d["close"] for d in data]
    for i in range(len(data)):
        if i >= period - 1:
            data[i][f"sma({period})"] = round(sum(closes[i-period+1:i+1]) / period, 6)
        else:
            data[i][f"sma({period})"] = None
    return data

def calc_rsi(data: List[dict], period: int) -> List[dict]:
    closes = [d["close"] for d in data]
    gains, losses = [], []
    for i in range(len(data)):
        if i == 0:
            gains.append(0); losses.append(0)
        else:
            change = closes[i] - closes[i-1]
            gains.append(max(0, change))
            losses.append(max(0, -change))
        if i >= period:
            avg_gain = sum(gains[i-period+1:i+1]) / period
            avg_loss = sum(losses[i-period+1:i+1]) / period
            if avg_loss == 0:
                rsi = 100
            else:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))
            data[i][f"rsi({period})"] = round(rsi, 2)
        else:
            data[i][f"rsi({period})"] = None
    return data

def calc_atr(data: List[dict], period: int) -> List[dict]:
    trs = []
    for i in range(len(data)):
        if i == 0:
            tr = data[i]["high"] - data[i]["low"]
        else:
            tr = max(
                data[i]["high"] - data[i]["low"],
                abs(data[i]["high"] - data[i-1]["close"]),
                abs(data[i]["low"] - data[i-1]["close"])
            )
        trs.append(tr)
        if i >= period - 1:
            data[i][f"atr({period})"] = round(sum(trs[i-period+1:i+1]) / period, 6)
        else:
            data[i][f"atr({period})"] = None
    return data

def calc_bollinger(data: List[dict], period: int, std_dev: float) -> List[dict]:
    closes = [d["close"] for d in data]
    for i in range(len(data)):
        if i >= period - 1:
            window = closes[i-period+1:i+1]
            mean = sum(window) / len(window)
            std = math.sqrt(sum((x - mean) ** 2 for x in window) / len(window))
            data[i]["bb_middle"] = round(mean, 6)
            data[i]["bb_upper"] = round(mean + std_dev * std, 6)
            data[i]["bb_lower"] = round(mean - std_dev * std, 6)
        else:
            data[i]["bb_middle"] = data[i]["bb_upper"] = data[i]["bb_lower"] = None
    return data


# ── ICT Concept Detection ─────────────────────────────────────────────────

def detect_fvg(data: List[dict]) -> List[dict]:
    """Detect Fair Value Gaps (bullish and bearish)."""
    for i in range(2, len(data)):
        gap_up = data[i]["low"] - data[i-2]["high"]
        gap_down = data[i-2]["low"] - data[i]["high"]
        data[i]["fvg_bullish"] = gap_up > 0
        data[i]["fvg_bearish"] = gap_down > 0
        data[i]["fvg_bullish_size"] = gap_up if gap_up > 0 else 0
        data[i]["fvg_bearish_size"] = gap_down if gap_down > 0 else 0
    return data

def detect_order_blocks(data: List[dict]) -> List[dict]:
    """Detect Order Blocks (bullish and bearish)."""
    for i in range(5, len(data) - 3):
        # Bullish OB: bearish candle followed by 2+ bullish candles
        if data[i]["close"] < data[i]["open"]:
            follow_up = sum(1 for j in range(1, 4) if data[i+j]["close"] > data[i+j]["open"])
            if follow_up >= 2:
                data[i]["ob_bullish"] = True
                data[i]["ob_bullish_high"] = data[i]["high"]
                data[i]["ob_bullish_low"] = data[i]["low"]
        # Bearish OB: bullish candle followed by 2+ bearish candles
        if data[i]["close"] > data[i]["open"]:
            follow_down = sum(1 for j in range(1, 4) if data[i+j]["close"] < data[i+j]["open"])
            if follow_down >= 2:
                data[i]["ob_bearish"] = True
                data[i]["ob_bearish_high"] = data[i]["high"]
                data[i]["ob_bearish_low"] = data[i]["low"]

    # Active OB zones - price interaction
    active_ob_bullish = []
    active_ob_bearish = []
    for i in range(len(data)):
        if data[i].get("ob_bullish"):
            active_ob_bullish.append((data[i]["high"], data[i]["low"]))
        if data[i].get("ob_bearish"):
            active_ob_bearish.append((data[i]["high"], data[i]["low"]))
        data[i]["price_at_ob_bullish"] = any(
            ob_low <= data[i]["low"] <= ob_high or ob_low <= data[i]["close"] <= ob_high
            for ob_high, ob_low in active_ob_bullish[-5:]
        )
        data[i]["price_at_ob_bearish"] = any(
            ob_low <= data[i]["low"] <= ob_high or ob_low <= data[i]["close"] <= ob_high
            for ob_high, ob_low in active_ob_bearish[-5:]
        )
    return data

def detect_swing_points(data: List[dict], lookback: int = 5) -> Tuple[List, List]:
    """Detect swing highs and lows."""
    swing_highs = []
    swing_lows = []
    for i in range(lookback, len(data) - lookback):
        if all(data[i]["high"] > data[i-j]["high"] for j in range(1, lookback+1)) and \
           all(data[i]["high"] > data[i+j]["high"] for j in range(1, lookback+1)):
            swing_highs.append((i, data[i]["high"]))
        if all(data[i]["low"] < data[i-j]["low"] for j in range(1, lookback+1)) and \
           all(data[i]["low"] < data[i+j]["low"] for j in range(1, lookback+1)):
            swing_lows.append((i, data[i]["low"]))
    return swing_highs, swing_lows

def detect_bos_choch(data: List[dict], swing_highs: List, swing_lows: List) -> List[dict]:
    """Detect Break of Structure (BOS) and Change of Character (CHoCH)."""
    for i in range(len(data)):
        data[i]["bos_bullish"] = False
        data[i]["bos_bearish"] = False
        data[i]["choch_bullish"] = False
        data[i]["choch_bearish"] = False

        recent_sh = [sh for sh in swing_highs if sh[0] < i]
        recent_sl = [sl for sl in swing_lows if sl[0] < i]

        # BOS: close beyond previous swing
        if len(recent_sh) >= 2 and data[i]["close"] > recent_sh[-1][1]:
            data[i]["bos_bullish"] = True
        if len(recent_sl) >= 2 and data[i]["close"] < recent_sl[-1][1]:
            data[i]["bos_bearish"] = True

        # CHoCH: after a series of higher highs, price breaks below a swing low (or vice versa)
        if len(recent_sl) >= 2 and recent_sl[-1][1] < recent_sl[-2][1]:
            if recent_sh and data[i]["close"] > recent_sh[-1][1]:
                data[i]["choch_bullish"] = True
        if len(recent_sh) >= 2 and recent_sh[-1][1] > recent_sh[-2][1]:
            if recent_sl and data[i]["close"] < recent_sl[-1][1]:
                data[i]["choch_bearish"] = True
    return data

def detect_liquidity_sweeps(data: List[dict], swing_highs: List, swing_lows: List) -> List[dict]:
    """Detect liquidity sweeps (stop hunts) - price sweeps a level then reverses."""
    for i in range(len(data)):
        data[i]["liquidity_sweep_bullish"] = False
        data[i]["liquidity_sweep_bearish"] = False
        data[i]["near_liquidity_low"] = False
        data[i]["near_liquidity_high"] = False

        recent_lows = sorted([(sl[1], sl[0]) for sl in swing_lows if sl[0] > len(data) - 100])
        recent_highs = sorted([(sh[1], sh[0]) for sh in swing_highs if sh[0] > len(data) - 100], reverse=True)

        if recent_lows:
            lowest_low = recent_lows[0][0]
            data[i]["near_liquidity_low"] = abs(data[i]["low"] - lowest_low) / lowest_low < 0.001
            # Sweep: price went below the low but closed above it
            if data[i]["low"] < lowest_low and data[i]["close"] > lowest_low:
                data[i]["liquidity_sweep_bullish"] = True

        if recent_highs:
            highest_high = recent_highs[0][0]
            data[i]["near_liquidity_high"] = abs(data[i]["high"] - highest_high) / highest_high < 0.001
            # Sweep: price went above the high but closed below it
            if data[i]["high"] > highest_high and data[i]["close"] < highest_high:
                data[i]["liquidity_sweep_bearish"] = True
    return data


# ── Smart Money Trap Strategy Definitions ─────────────────────────────────

def get_strategy_variations() -> List[Dict]:
    """
    Define Smart Money Trap strategy variations.
    Each variation combines different ICT concepts for trap detection.
    """
    variations = []

    # ── VARIATION 1: Classic Liquidity Sweep + CHoCH ──
    # The core trap: price sweeps liquidity, then CHoCH confirms reversal
    variations.append({
        "name": "SMT_Classic_Sweep_CHoCH",
        "description": "Classic Smart Money Trap: Liquidity Sweep + Change of Character",
        "indicators": [
            {"type": "ema", "parameters": {"period": 50}},
        ],
        "entry_signals": [
            {
                "type": "buy",
                "condition": {
                    "logic": "AND",
                    "conditions": [
                        {"left_operand": "liquidity_sweep_bullish", "operator": "==", "right_operand": "true"},
                        {"left_operand": "choch_bullish", "operator": "==", "right_operand": "true"},
                    ]
                },
                "confidence": 0.85
            },
            {
                "type": "sell",
                "condition": {
                    "logic": "AND",
                    "conditions": [
                        {"left_operand": "liquidity_sweep_bearish", "operator": "==", "right_operand": "true"},
                        {"left_operand": "choch_bearish", "operator": "==", "right_operand": "true"},
                    ]
                },
                "confidence": 0.85
            }
        ],
        "exit_signals": [
            {
                "type": "close_long",
                "condition": {
                    "logic": "OR",
                    "conditions": [
                        {"left_operand": "choch_bearish", "operator": "==", "right_operand": "true"},
                        {"left_operand": "position_bars_held", "operator": ">", "right_operand": "20"},
                    ]
                },
                "confidence": 0.7
            },
            {
                "type": "close_short",
                "condition": {
                    "logic": "OR",
                    "conditions": [
                        {"left_operand": "choch_bullish", "operator": "==", "right_operand": "true"},
                        {"left_operand": "position_bars_held", "operator": ">", "right_operand": "20"},
                    ]
                },
                "confidence": 0.7
            }
        ],
        "risk_management": {"stop_loss": 30, "take_profit": 60, "trailing_stop": 0},
    })

    # ── VARIATION 2: Liquidity Sweep + FVG Entry ──
    # Sweep triggers, enter at FVG for better R:R
    variations.append({
        "name": "SMT_Sweep_FVG",
        "description": "Liquidity Sweep triggers, enter at Fair Value Gap",
        "indicators": [
            {"type": "ema", "parameters": {"period": 50}},
        ],
        "entry_signals": [
            {
                "type": "buy",
                "condition": {
                    "logic": "AND",
                    "conditions": [
                        {"left_operand": "liquidity_sweep_bullish", "operator": "==", "right_operand": "true"},
                        {"left_operand": "fvg_bullish", "operator": "==", "right_operand": "true"},
                    ]
                },
                "confidence": 0.8
            },
            {
                "type": "sell",
                "condition": {
                    "logic": "AND",
                    "conditions": [
                        {"left_operand": "liquidity_sweep_bearish", "operator": "==", "right_operand": "true"},
                        {"left_operand": "fvg_bearish", "operator": "==", "right_operand": "true"},
                    ]
                },
                "confidence": 0.8
            }
        ],
        "exit_signals": [
            {
                "type": "close_long",
                "condition": {
                    "logic": "OR",
                    "conditions": [
                        {"left_operand": "fvg_bearish", "operator": "==", "right_operand": "true"},
                        {"left_operand": "position_bars_held", "operator": ">", "right_operand": "25"},
                    ]
                },
                "confidence": 0.65
            },
            {
                "type": "close_short",
                "condition": {
                    "logic": "OR",
                    "conditions": [
                        {"left_operand": "fvg_bullish", "operator": "==", "right_operand": "true"},
                        {"left_operand": "position_bars_held", "operator": ">", "right_operand": "25"},
                    ]
                },
                "confidence": 0.65
            }
        ],
        "risk_management": {"stop_loss": 25, "take_profit": 75, "trailing_stop": 0},
    })

    # ── VARIATION 3: Sweep + Order Block ──
    # Sweep triggers, enter at Order Block zone
    variations.append({
        "name": "SMT_Sweep_OB",
        "description": "Liquidity Sweep + Order Block confirmation",
        "indicators": [
            {"type": "ema", "parameters": {"period": 50}},
        ],
        "entry_signals": [
            {
                "type": "buy",
                "condition": {
                    "logic": "AND",
                    "conditions": [
                        {"left_operand": "liquidity_sweep_bullish", "operator": "==", "right_operand": "true"},
                        {"left_operand": "price_at_ob_bullish", "operator": "==", "right_operand": "true"},
                    ]
                },
                "confidence": 0.8
            },
            {
                "type": "sell",
                "condition": {
                    "logic": "AND",
                    "conditions": [
                        {"left_operand": "liquidity_sweep_bearish", "operator": "==", "right_operand": "true"},
                        {"left_operand": "price_at_ob_bearish", "operator": "==", "right_operand": "true"},
                    ]
                },
                "confidence": 0.8
            }
        ],
        "exit_signals": [
            {
                "type": "close_long",
                "condition": {
                    "logic": "OR",
                    "conditions": [
                        {"left_operand": "bos_bearish", "operator": "==", "right_operand": "true"},
                        {"left_operand": "position_bars_held", "operator": ">", "right_operand": "30"},
                    ]
                },
                "confidence": 0.65
            },
            {
                "type": "close_short",
                "condition": {
                    "logic": "OR",
                    "conditions": [
                        {"left_operand": "bos_bullish", "operator": "==", "right_operand": "true"},
                        {"left_operand": "position_bars_held", "operator": ">", "right_operand": "30"},
                    ]
                },
                "confidence": 0.65
            }
        ],
        "risk_management": {"stop_loss": 35, "take_profit": 70, "trailing_stop": 0},
    })

    # ── VARIATION 4: Full Confirmation (Sweep + CHoCH + FVG) ──
    # Most selective: all 3 confirmations required
    variations.append({
        "name": "SMT_Full_Confirmation",
        "description": "Full confirmation: Sweep + CHoCH + FVG (most selective)",
        "indicators": [
            {"type": "ema", "parameters": {"period": 50}},
            {"type": "rsi", "parameters": {"period": 14, "overbought": 70, "oversold": 30}},
        ],
        "entry_signals": [
            {
                "type": "buy",
                "condition": {
                    "logic": "AND",
                    "conditions": [
                        {"left_operand": "liquidity_sweep_bullish", "operator": "==", "right_operand": "true"},
                        {"left_operand": "choch_bullish", "operator": "==", "right_operand": "true"},
                        {"left_operand": "fvg_bullish", "operator": "==", "right_operand": "true"},
                    ]
                },
                "confidence": 0.9
            },
            {
                "type": "sell",
                "condition": {
                    "logic": "AND",
                    "conditions": [
                        {"left_operand": "liquidity_sweep_bearish", "operator": "==", "right_operand": "true"},
                        {"left_operand": "choch_bearish", "operator": "==", "right_operand": "true"},
                        {"left_operand": "fvg_bearish", "operator": "==", "right_operand": "true"},
                    ]
                },
                "confidence": 0.9
            }
        ],
        "exit_signals": [
            {
                "type": "close_long",
                "condition": {
                    "logic": "OR",
                    "conditions": [
                        {"left_operand": "choch_bearish", "operator": "==", "right_operand": "true"},
                        {"left_operand": "position_bars_held", "operator": ">", "right_operand": "15"},
                    ]
                },
                "confidence": 0.7
            },
            {
                "type": "close_short",
                "condition": {
                    "logic": "OR",
                    "conditions": [
                        {"left_operand": "choch_bullish", "operator": "==", "right_operand": "true"},
                        {"left_operand": "position_bars_held", "operator": ">", "right_operand": "15"},
                    ]
                },
                "confidence": 0.7
            }
        ],
        "risk_management": {"stop_loss": 20, "take_profit": 60, "trailing_stop": 0},
    })

    # ── VARIATION 5: Sweep + RSI Divergence ──
    # Sweep triggers, RSI confirms oversold/overbought
    variations.append({
        "name": "SMT_Sweep_RSI",
        "description": "Liquidity Sweep + RSI confirmation",
        "indicators": [
            {"type": "ema", "parameters": {"period": 50}},
            {"type": "rsi", "parameters": {"period": 14, "overbought": 70, "oversold": 30}},
        ],
        "entry_signals": [
            {
                "type": "buy",
                "condition": {
                    "logic": "AND",
                    "conditions": [
                        {"left_operand": "liquidity_sweep_bullish", "operator": "==", "right_operand": "true"},
                        {"left_operand": "rsi(14)", "operator": "<", "right_operand": "35"},
                    ]
                },
                "confidence": 0.75
            },
            {
                "type": "sell",
                "condition": {
                    "logic": "AND",
                    "conditions": [
                        {"left_operand": "liquidity_sweep_bearish", "operator": "==", "right_operand": "true"},
                        {"left_operand": "rsi(14)", "operator": ">", "right_operand": "65"},
                    ]
                },
                "confidence": 0.75
            }
        ],
        "exit_signals": [
            {
                "type": "close_long",
                "condition": {
                    "logic": "OR",
                    "conditions": [
                        {"left_operand": "rsi(14)", "operator": ">", "right_operand": "65"},
                        {"left_operand": "position_bars_held", "operator": ">", "right_operand": "20"},
                    ]
                },
                "confidence": 0.65
            },
            {
                "type": "close_short",
                "condition": {
                    "logic": "OR",
                    "conditions": [
                        {"left_operand": "rsi(14)", "operator": "<", "right_operand": "35"},
                        {"left_operand": "position_bars_held", "operator": ">", "right_operand": "20"},
                    ]
                },
                "confidence": 0.65
            }
        ],
        "risk_management": {"stop_loss": 30, "take_profit": 60, "trailing_stop": 0},
    })

    # ── VARIATION 6: Sweep + Bollinger Band ──
    # Sweep triggers, price at extreme BB for mean reversion
    variations.append({
        "name": "SMT_Sweep_BB",
        "description": "Liquidity Sweep + Bollinger Band extreme",
        "indicators": [
            {"type": "ema", "parameters": {"period": 50}},
            {"type": "bollinger_bands", "parameters": {"period": 20, "std_dev": 2.0}},
        ],
        "entry_signals": [
            {
                "type": "buy",
                "condition": {
                    "logic": "AND",
                    "conditions": [
                        {"left_operand": "liquidity_sweep_bullish", "operator": "==", "right_operand": "true"},
                        {"left_operand": "close", "operator": "<", "right_operand": "bb_lower"},
                    ]
                },
                "confidence": 0.75
            },
            {
                "type": "sell",
                "condition": {
                    "logic": "AND",
                    "conditions": [
                        {"left_operand": "liquidity_sweep_bearish", "operator": "==", "right_operand": "true"},
                        {"left_operand": "close", "operator": ">", "right_operand": "bb_upper"},
                    ]
                },
                "confidence": 0.75
            }
        ],
        "exit_signals": [
            {
                "type": "close_long",
                "condition": {
                    "logic": "OR",
                    "conditions": [
                        {"left_operand": "close", "operator": ">", "right_operand": "bb_middle"},
                        {"left_operand": "position_bars_held", "operator": ">", "right_operand": "15"},
                    ]
                },
                "confidence": 0.65
            },
            {
                "type": "close_short",
                "condition": {
                    "logic": "OR",
                    "conditions": [
                        {"left_operand": "close", "operator": "<", "right_operand": "bb_middle"},
                        {"left_operand": "position_bars_held", "operator": ">", "right_operand": "15"},
                    ]
                },
                "confidence": 0.65
            }
        ],
        "risk_management": {"stop_loss": 25, "take_profit": 50, "trailing_stop": 0},
    })

    # ── VARIATION 7: Sweep + EMA Trend Filter ──
    # Only take sweeps in direction of EMA trend
    variations.append({
        "name": "SMT_Sweep_Trend",
        "description": "Liquidity Sweep with EMA trend filter",
        "indicators": [
            {"type": "ema", "parameters": {"period": 50}},
            {"type": "ema", "parameters": {"period": 200}},
        ],
        "entry_signals": [
            {
                "type": "buy",
                "condition": {
                    "logic": "AND",
                    "conditions": [
                        {"left_operand": "liquidity_sweep_bullish", "operator": "==", "right_operand": "true"},
                        {"left_operand": "close", "operator": ">", "right_operand": "ema(200)"},
                        {"left_operand": "ema(50)", "operator": ">", "right_operand": "ema(200)"},
                    ]
                },
                "confidence": 0.8
            },
            {
                "type": "sell",
                "condition": {
                    "logic": "AND",
                    "conditions": [
                        {"left_operand": "liquidity_sweep_bearish", "operator": "==", "right_operand": "true"},
                        {"left_operand": "close", "operator": "<", "right_operand": "ema(200)"},
                        {"left_operand": "ema(50)", "operator": "<", "right_operand": "ema(200)"},
                    ]
                },
                "confidence": 0.8
            }
        ],
        "exit_signals": [
            {
                "type": "close_long",
                "condition": {
                    "logic": "OR",
                    "conditions": [
                        {"left_operand": "close", "operator": "<", "right_operand": "ema(50)"},
                        {"left_operand": "position_bars_held", "operator": ">", "right_operand": "25"},
                    ]
                },
                "confidence": 0.65
            },
            {
                "type": "close_short",
                "condition": {
                    "logic": "OR",
                    "conditions": [
                        {"left_operand": "close", "operator": ">", "right_operand": "ema(50)"},
                        {"left_operand": "position_bars_held", "operator": ">", "right_operand": "25"},
                    ]
                },
                "confidence": 0.65
            }
        ],
        "risk_management": {"stop_loss": 35, "take_profit": 70, "trailing_stop": 0},
    })

    # ── VARIATION 8: Sweep + ATR-based SL/TP ──
    # Use ATR for dynamic stop loss and take profit
    variations.append({
        "name": "SMT_Sweep_ATR",
        "description": "Liquidity Sweep with ATR-based dynamic SL/TP",
        "indicators": [
            {"type": "ema", "parameters": {"period": 50}},
            {"type": "atr", "parameters": {"period": 14}},
        ],
        "entry_signals": [
            {
                "type": "buy",
                "condition": {
                    "logic": "AND",
                    "conditions": [
                        {"left_operand": "liquidity_sweep_bullish", "operator": "==", "right_operand": "true"},
                        {"left_operand": "choch_bullish", "operator": "==", "right_operand": "true"},
                    ]
                },
                "confidence": 0.85
            },
            {
                "type": "sell",
                "condition": {
                    "logic": "AND",
                    "conditions": [
                        {"left_operand": "liquidity_sweep_bearish", "operator": "==", "right_operand": "true"},
                        {"left_operand": "choch_bearish", "operator": "==", "right_operand": "true"},
                    ]
                },
                "confidence": 0.85
            }
        ],
        "exit_signals": [
            {
                "type": "close_long",
                "condition": {
                    "logic": "OR",
                    "conditions": [
                        {"left_operand": "choch_bearish", "operator": "==", "right_operand": "true"},
                        {"left_operand": "position_bars_held", "operator": ">", "right_operand": "20"},
                    ]
                },
                "confidence": 0.7
            },
            {
                "type": "close_short",
                "condition": {
                    "logic": "OR",
                    "conditions": [
                        {"left_operand": "choch_bullish", "operator": "==", "right_operand": "true"},
                        {"left_operand": "position_bars_held", "operator": ">", "right_operand": "20"},
                    ]
                },
                "confidence": 0.7
            }
        ],
        "risk_management": {"stop_loss": 40, "take_profit": 80, "trailing_stop": 30},
    })

    return variations


# ── Backtest Engine ───────────────────────────────────────────────────────

class Trade:
    def __init__(self, entry_price, entry_date, direction, size=1.0):
        self.entry_price = entry_price
        self.entry_date = entry_date
        self.direction = direction
        self.size = size
        self.exit_price = None
        self.exit_date = None
        self.stop_loss = None
        self.take_profit = None

    @property
    def pnl(self):
        if self.exit_price is None:
            return 0
        if self.direction == "long":
            return (self.exit_price - self.entry_price) * self.size
        return (self.entry_price - self.exit_price) * self.size

    @property
    def return_pct(self):
        if self.entry_price == 0:
            return 0
        return self.pnl / (self.entry_price * self.size)

    @property
    def is_win(self):
        return self.pnl > 0

    @property
    def is_loss(self):
        return self.pnl < 0


def run_backtest(data: List[dict], strategy: Dict, initial_capital: float = 10000.0,
                 commission: float = 0.001) -> Dict[str, Any]:
    """Run backtest on pre-computed data with ICT concepts already detected."""
    trades: List[Trade] = []
    equity_curve: List[float] = []
    position = None
    equity = initial_capital
    position_size = 1.0
    rm = strategy.get("risk_management", {})
    stop_loss = rm.get("stop_loss", 0)
    take_profit = rm.get("take_profit", 0)
    trailing_stop = rm.get("trailing_stop", 0)
    highest_since_entry = 0
    bars_since_entry = 0

    entry_signals = strategy.get("entry_signals", [])
    exit_signals = strategy.get("exit_signals", [])

    for i in range(1, len(data)):
        bar = data[i]
        prev_bar = data[i - 1]
        bar["_position_bars_held"] = bars_since_entry if position else 0

        # ── Check exits ──
        if position is not None:
            exit_reason = None
            exit_price = None

            if position["direction"] == "long":
                if stop_loss and bar["low"] <= position.get("sl", 0):
                    exit_price = max(position.get("sl", bar["open"]), bar["low"])
                    exit_reason = "stop_loss"
                elif take_profit and bar["high"] >= position.get("tp", float("inf")):
                    exit_price = min(position.get("tp", bar["open"]), bar["high"])
                    exit_reason = "take_profit"
                elif trailing_stop:
                    highest_since_entry = max(highest_since_entry, bar["high"])
                    if bar["low"] <= highest_since_entry - trailing_stop:
                        exit_reason = "trailing_stop"
            else:  # short
                if stop_loss and bar["high"] >= position.get("sl", float("inf")):
                    exit_price = min(position.get("sl", bar["open"]), bar["high"])
                    exit_reason = "stop_loss"
                elif take_profit and bar["low"] <= position.get("tp", 0):
                    exit_price = max(position.get("tp", bar["open"]), bar["low"])
                    exit_reason = "take_profit"

            # Exit signals
            if exit_reason is None and exit_signals:
                for sig in exit_signals:
                    sig_type = sig.get("type", "close_all")
                    if sig_type == "close_long" and position["direction"] != "long":
                        continue
                    if sig_type == "close_short" and position["direction"] != "short":
                        continue
                    if _check_signal(bar, prev_bar, sig):
                        exit_price = bar["open"]
                        exit_reason = "signal"
                        break

            if exit_reason:
                trade = Trade(
                    entry_price=position["entry"],
                    entry_date=position["date"],
                    direction=position["direction"],
                    size=position_size
                )
                trade.exit_price = exit_price
                trade.exit_date = bar["date"]
                pnl = trade.pnl - (trade.entry_price + exit_price) * commission * position_size
                equity += pnl
                trades.append(trade)
                position = None
                highest_since_entry = 0
                bars_since_entry = 0

        # ── Check entries ──
        if position is None and entry_signals:
            for sig in entry_signals:
                if _check_signal(bar, prev_bar, sig):
                    direction = "long" if sig.get("type") == "buy" else "short"
                    entry_price = bar["open"]
                    sl = None
                    tp = None
                    if direction == "long":
                        if stop_loss:
                            sl = entry_price - stop_loss * 0.0001  # Convert pips to price
                        if take_profit:
                            tp = entry_price + take_profit * 0.0001
                    else:
                        if stop_loss:
                            sl = entry_price + stop_loss * 0.0001
                        if take_profit:
                            tp = entry_price - take_profit * 0.0001
                    position = {
                        "direction": direction,
                        "entry": entry_price,
                        "date": bar["date"],
                        "sl": sl,
                        "tp": tp,
                    }
                    highest_since_entry = entry_price
                    bars_since_entry = 0
                    break

        if position:
            bars_since_entry += 1
        equity_curve.append(round(equity, 2))

    # Close any open position at end
    if position is not None:
        trade = Trade(
            entry_price=position["entry"],
            entry_date=position["date"],
            direction=position["direction"],
            size=position_size
        )
        trade.exit_price = data[-1]["close"]
        trade.exit_date = data[-1]["date"]
        pnl = trade.pnl - (trade.entry_price + data[-1]["close"]) * commission * position_size
        equity += pnl
        trades.append(trade)

    # Calculate metrics
    metrics = _calculate_metrics(trades, equity_curve, initial_capital)

    return {
        "metrics": metrics,
        "trades": len(trades),
        "equity_curve": equity_curve,
        "final_equity": equity_curve[-1] if equity_curve else initial_capital,
    }


def _check_signal(bar: dict, prev_bar: dict, signal: dict) -> bool:
    condition = signal.get("condition", {})
    logic = condition.get("logic", "AND")
    conditions = condition.get("conditions", [])
    results = [_evaluate_condition(bar, prev_bar, c) for c in conditions]
    if not results:
        return False
    return all(results) if logic == "AND" else any(results)


def _evaluate_condition(bar: dict, prev_bar: dict, cond: dict) -> bool:
    left = _resolve(cond.get("left_operand", ""), bar, prev_bar)
    right = _resolve(cond.get("right_operand", ""), bar, prev_bar)
    op = cond.get("operator", "==")
    if left is None or right is None:
        return False
    try:
        lv, rv = float(left), float(right)
    except (ValueError, TypeError):
        return False
    if op == ">":
        return lv > rv
    elif op == "<":
        return lv < rv
    elif op == "==":
        return abs(lv - rv) < 1e-10
    elif op == ">=":
        return lv >= rv
    elif op == "<=":
        return lv <= rv
    elif op == "crosses_above":
        pl = _resolve(cond.get("left_operand", ""), prev_bar, None)
        pr = _resolve(cond.get("right_operand", ""), prev_bar, None)
        if pl is None or pr is None:
            return False
        return float(pl) <= float(pr) and lv > rv
    elif op == "crosses_below":
        pl = _resolve(cond.get("left_operand", ""), prev_bar, None)
        pr = _resolve(cond.get("right_operand", ""), prev_bar, None)
        if pl is None or pr is None:
            return False
        return float(pl) >= float(pr) and lv < rv
    return False


def _resolve(operand: str, bar: dict, prev_bar: dict) -> Optional[float]:
    if bar is None:
        return None
    operand = str(operand).strip().lower()
    if operand == "close":
        return bar.get("close")
    elif operand == "open":
        return bar.get("open")
    elif operand == "high":
        return bar.get("high")
    elif operand == "low":
        return bar.get("low")
    elif operand == "volume":
        return bar.get("volume")
    elif operand == "position_bars_held":
        return bar.get("_position_bars_held")
    elif operand in bar:
        return bar[operand]
    if operand == "upper_bb":
        return bar.get("bb_upper")
    elif operand == "lower_bb":
        return bar.get("bb_lower")
    elif operand == "middle_bb":
        return bar.get("bb_middle")
    elif operand == "macd_line":
        return bar.get("macd_line")
    elif operand == "macd_signal":
        return bar.get("macd_signal")
    try:
        return float(operand)
    except ValueError:
        if operand == "true":
            return 1.0
        if operand == "false":
            return 0.0
        return None


def _calculate_metrics(trades: List[Trade], equity_curve: List[float], initial_capital: float) -> Dict:
    if not trades:
        return {
            "total_return": 0, "sharpe_ratio": 0, "sortino_ratio": 0, "max_drawdown": 0,
            "win_rate": 0, "profit_factor": 0, "total_trades": 0, "avg_trade": 0,
            "calmar_ratio": 0, "omega_ratio": 0, "expectancy": 0, "net_profit": 0,
        }

    returns = [t.return_pct for t in trades]
    wins = [t for t in trades if t.is_win]
    losses = [t for t in trades if t.is_loss]
    gross_profit = sum(t.pnl for t in wins) if wins else 0
    gross_loss = abs(sum(t.pnl for t in losses)) if losses else 0
    net_profit = gross_profit - gross_loss

    if equity_curve and len(equity_curve) > 0:
        total_return = (equity_curve[-1] - initial_capital) / initial_capital
    else:
        total_return = 0

    win_rate = len(wins) / len(trades) if trades else 0
    avg_trade = sum(returns) / len(returns) if returns else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

    if len(returns) > 1:
        arr = np.array(returns)
        std = np.std(arr, ddof=1)
        sharpe = (np.mean(arr) / std * math.sqrt(252)) if std > 0 else 0
        downside = [r for r in returns if r < 0]
        dstd = np.std(downside, ddof=1) if len(downside) > 1 else 0
        sortino = (np.mean(arr) / dstd * math.sqrt(252)) if dstd > 0 else 0
    else:
        sharpe = sortino = 0

    max_dd = _max_drawdown(equity_curve)
    calmar = (total_return / max_dd) if max_dd > 0 else 0

    if returns:
        threshold = 0
        gains_above = sum(r - threshold for r in returns if r > threshold)
        losses_below = sum(threshold - r for r in returns if r < threshold)
        omega = gains_above / losses_below if losses_below > 0 else 0
    else:
        omega = 0

    return {
        "total_return": round(total_return * 100, 2) or 0.0,
        "sharpe_ratio": round(float(sharpe), 4) or 0.0,
        "sortino_ratio": round(float(sortino), 4) or 0.0,
        "max_drawdown": round(max_dd * 100, 2) or 0.0,
        "win_rate": round(win_rate * 100, 2) or 0.0,
        "profit_factor": round(float(profit_factor), 4) or 0.0,
        "total_trades": len(trades),
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "avg_trade": round(avg_trade * 100, 4),
        "calmar_ratio": round(float(calmar), 4) or 0.0,
        "omega_ratio": round(float(omega), 4) or 0.0,
        "expectancy": round((win_rate * (gross_profit / len(wins) if wins else 0) +
                            (1 - win_rate) * (-gross_loss / len(losses) if losses else 0)), 4),
        "net_profit": round(net_profit, 4),
        "gross_profit": round(gross_profit, 4),
        "gross_loss": round(gross_loss, 4),
    }


def _max_drawdown(equity_curve: List[float]) -> float:
    if not equity_curve:
        return 0
    peak = equity_curve[0]
    max_dd = 0
    for eq in equity_curve:
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd
    return max_dd


# ── Main Execution ────────────────────────────────────────────────────────

def prepare_data(symbol: str, n_bars: int = 8000) -> List[dict]:
    """Generate and prepare data with all ICT concepts pre-computed."""
    data = generate_synthetic_data(symbol, "2022-01-01", "2024-01-01", n_bars)

    # Calculate indicators
    data = calc_ema(data, 50)
    data = calc_ema(data, 200)
    data = calc_rsi(data, 14)
    data = calc_atr(data, 14)
    data = calc_bollinger(data, 20, 2.0)

    # Detect ICT concepts
    data = detect_fvg(data)
    data = detect_order_blocks(data)
    swing_highs, swing_lows = detect_swing_points(data, lookback=5)
    data = detect_bos_choch(data, swing_highs, swing_lows)
    data = detect_liquidity_sweeps(data, swing_highs, swing_lows)

    return data


def score_strategy(metrics: Dict) -> float:
    """
    Score a strategy variation. Higher is better.
    Balances return, consistency, and risk.
    Penalizes overfitting indicators.
    """
    if metrics["total_trades"] < 10:
        return -999  # Too few trades = unreliable

    score = 0

    # Profitability (40% weight)
    score += metrics["total_return"] * 2
    score += metrics["net_profit"] * 0.5

    # Risk-adjusted return (30% weight)
    score += metrics["sharpe_ratio"] * 10
    score += metrics["sortino_ratio"] * 5
    score -= metrics["max_drawdown"] * 0.5

    # Consistency (20% weight)
    score += metrics["win_rate"] * 0.3
    score += metrics["profit_factor"] * 5
    score += metrics["omega_ratio"] * 3

    # Penalize too few trades (overfitting risk)
    if metrics["total_trades"] < 30:
        score *= 0.5
    elif metrics["total_trades"] < 50:
        score *= 0.8

    # Penalize extreme drawdowns
    if metrics["max_drawdown"] > 5:
        score -= (metrics["max_drawdown"] - 5) * 2

    return score


def main():
    print("=" * 70)
    print("SMART MONEY TRAP STRATEGY - VARIATION TESTER")
    print("=" * 70)
    print()

    # Prepare data once
    print("[1/4] Preparing data with ICT concept detection...")
    data = prepare_data("EURUSD", n_bars=8000)
    print(f"  Data: {len(data)} bars, indicators + ICT concepts computed")
    print()

    # Get strategy variations
    print("[2/4] Generating strategy variations...")
    variations = get_strategy_variations()
    print(f"  {len(variations)} variations defined")
    for v in variations:
        print(f"  - {v['name']}: {v['description']}")
    print()

    # Backtest each variation
    print("[3/4] Backtesting all variations...")
    print("-" * 70)
    results = []
    for i, strat in enumerate(variations):
        result = run_backtest(data, strat)
        metrics = result["metrics"]
        score = score_strategy(metrics)
        results.append({
            "strategy": strat,
            "metrics": metrics,
            "score": score,
            "trades": result["trades"],
        })
        print(f"  [{i+1}/{len(variations)}] {strat['name']}")
        print(f"    Return: {metrics['total_return']}% | Sharpe: {metrics['sharpe_ratio']} | "
              f"WinRate: {metrics['win_rate']}% | PF: {metrics['profit_factor']} | "
              f"Trades: {metrics['total_trades']} | Score: {score:.1f}")
    print()

    # Sort by score
    results.sort(key=lambda x: x["score"], reverse=True)

    # Display ranking
    print("[4/4] RANKING (best to worst):")
    print("=" * 70)
    for rank, r in enumerate(results, 1):
        m = r["metrics"]
        marker = " <<< BEST" if rank == 1 else ""
        print(f"  #{rank} {r['strategy']['name']}{marker}")
        print(f"     Return: {m['total_return']}% | Sharpe: {m['sharpe_ratio']} | "
              f"Sortino: {m['sortino_ratio']} | MaxDD: {m['max_drawdown']}%")
        print(f"     WinRate: {m['win_rate']}% | PF: {m['profit_factor']} | "
              f"Omega: {m['omega_ratio']} | Trades: {m['total_trades']} "
              f"(W:{m['winning_trades']} L:{m['losing_trades']})")
        print(f"     Net Profit: {m['net_profit']} | Score: {r['score']:.1f}")
        print()

    # Best strategy
    best = results[0]
    print("=" * 70)
    print(f"BEST STRATEGY: {best['strategy']['name']}")
    print(f"Description: {best['strategy']['description']}")
    print(f"Score: {best['score']:.1f}")
    print()

    # Save results
    output = {
        "best_strategy": best["strategy"],
        "best_metrics": best["metrics"],
        "best_score": best["score"],
        "all_results": [
            {
                "name": r["strategy"]["name"],
                "score": r["score"],
                "metrics": r["metrics"],
            }
            for r in results
        ],
    }

    with open("/root/trading-strategy-ai-platform/smt_results.json", "w") as f:
        json.dump(output, f, indent=2, default=str)
    print("Results saved to: /root/trading-strategy-ai-platform/smt_results.json")

    return best["strategy"], best["metrics"]


if __name__ == "__main__":
    best_strat, best_metrics = main()
