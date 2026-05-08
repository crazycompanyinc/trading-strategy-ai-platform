"""
Smart Money Trap - Full Strategy Research & MT5 Generation
==========================================================
Tests multiple ICT-based trap strategy variations with parameter sweeps,
finds the best combination, and generates production-ready MT5 code.
"""
import json
import math
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple, Optional

import numpy as np

# ── Synthetic Data with Realistic Price Action ────────────────────────────

def generate_realistic_data(symbol: str, n_bars: int = 10000, seed: int = 42) -> List[Dict]:
    """
    Generate synthetic data with more realistic price action including
    trends, consolidations, and occasional stop-hunt patterns.
    """
    random.seed(seed)
    np.random.seed(seed)

    initial_prices = {
        "EURUSD": 1.1000, "GBPUSD": 1.2500, "USDJPY": 135.0,
        "XAUUSD": 1900.0, "BTCUSD": 30000.0
    }
    price = initial_prices.get(symbol, 1.0)
    volatilities = {
        "EURUSD": 0.0010, "GBPUSD": 0.0012, "USDJPY": 0.0010,
        "XAUUSD": 0.012, "BTCUSD": 0.035
    }
    vol = volatilities.get(symbol, 0.001)
    start = datetime(2020, 1, 1)
    data = []

    # Create trending and ranging periods
    trend = 0
    trend_duration = 0

    for i in range(n_bars):
        date = start + timedelta(hours=i)

        # Change trend periodically
        if trend_duration <= 0:
            trend = random.choice([-0.0001, -0.00005, 0, 0.00005, 0.0001])
            trend_duration = random.randint(100, 500)
        trend_duration -= 1

        # Occasional stop-hunt: sharp move then reversal
        stop_hunt = 0
        if random.random() < 0.02:  # 2% chance of stop hunt
            direction = random.choice([-1, 1])
            stop_hunt = direction * vol * random.uniform(2, 4)

        shock = np.random.normal(0, 1)
        ret = trend + vol * shock + stop_hunt

        # Add mean reversion after stop hunts
        if stop_hunt != 0 and random.random() < 0.7:
            ret -= stop_hunt * random.uniform(0.5, 1.0)  # Partial reversal

        open_p = price
        close_p = price * (1 + ret)
        high_p = max(open_p, close_p) * (1 + abs(np.random.normal(0, vol * 0.3)))
        low_p = min(open_p, close_p) * (1 - abs(np.random.normal(0, vol * 0.3)))
        volume = int(np.random.lognormal(10, 1.5))

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


# ── Indicators ─────────────────────────────────────────────────────────────

def calc_ema(data, period):
    closes = [d["close"] for d in data]
    mult = 2.0 / (period + 1)
    ema = closes[0]
    for i in range(len(data)):
        if i > 0:
            ema = (closes[i] - ema) * mult + ema
        data[i][f"ema({period})"] = round(ema, 6)
    return data

def calc_rsi(data, period):
    closes = [d["close"] for d in data]
    gains, losses = [], []
    for i in range(len(data)):
        if i == 0:
            gains.append(0); losses.append(0)
        else:
            change = closes[i] - closes[i-1]
            gains.append(max(0, change)); losses.append(max(0, -change))
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

def calc_atr(data, period):
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

def calc_bollinger(data, period, std_dev):
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


# ── ICT Concept Detection (More Sensitive) ────────────────────────────────

def detect_fvg(data):
    for i in range(2, len(data)):
        gap_up = data[i]["low"] - data[i-2]["high"]
        gap_down = data[i-2]["low"] - data[i]["high"]
        data[i]["fvg_bullish"] = gap_up > 0
        data[i]["fvg_bearish"] = gap_down > 0
    return data

def detect_order_blocks(data):
    for i in range(3, len(data) - 2):
        if data[i]["close"] < data[i]["open"]:
            follow_up = sum(1 for j in range(1, 3) if data[i+j]["close"] > data[i+j]["open"])
            if follow_up >= 2:
                data[i]["ob_bullish"] = True
                data[i]["ob_bullish_high"] = data[i]["high"]
                data[i]["ob_bullish_low"] = data[i]["low"]
        if data[i]["close"] > data[i]["open"]:
            follow_down = sum(1 for j in range(1, 3) if data[i+j]["close"] < data[i+j]["open"])
            if follow_down >= 2:
                data[i]["ob_bearish"] = True
                data[i]["ob_bearish_high"] = data[i]["high"]
                data[i]["ob_bearish_low"] = data[i]["low"]

    active_ob_bullish = []
    active_ob_bearish = []
    for i in range(len(data)):
        if data[i].get("ob_bullish"):
            active_ob_bullish.append((data[i]["high"], data[i]["low"]))
        if data[i].get("ob_bearish"):
            active_ob_bearish.append((data[i]["high"], data[i]["low"]))
        data[i]["price_at_ob_bullish"] = any(
            ob_low <= data[i]["low"] <= ob_high or ob_low <= data[i]["close"] <= ob_high
            for ob_high, ob_low in active_ob_bullish[-10:]
        )
        data[i]["price_at_ob_bearish"] = any(
            ob_low <= data[i]["low"] <= ob_high or ob_low <= data[i]["close"] <= ob_high
            for ob_high, ob_low in active_ob_bearish[-10:]
        )
    return data

def detect_swing_points(data, lookback=3):
    swing_highs = []
    swing_lows = []
    for i in range(lookback, len(data) - lookback):
        is_sh = all(data[i]["high"] >= data[i-j]["high"] for j in range(1, lookback+1)) and \
                all(data[i]["high"] >= data[i+j]["high"] for j in range(1, lookback+1))
        is_sl = all(data[i]["low"] <= data[i-j]["low"] for j in range(1, lookback+1)) and \
                all(data[i]["low"] <= data[i+j]["low"] for j in range(1, lookback+1))
        if is_sh:
            swing_highs.append((i, data[i]["high"]))
        if is_sl:
            swing_lows.append((i, data[i]["low"]))
    return swing_highs, swing_lows

def detect_bos_choch(data, swing_highs, swing_lows):
    for i in range(len(data)):
        data[i]["bos_bullish"] = False
        data[i]["bos_bearish"] = False
        data[i]["choch_bullish"] = False
        data[i]["choch_bearish"] = False

        recent_sh = [sh for sh in swing_highs if sh[0] < i]
        recent_sl = [sl for sl in swing_lows if sl[0] < i]

        if len(recent_sh) >= 2 and data[i]["close"] > recent_sh[-1][1]:
            data[i]["bos_bullish"] = True
        if len(recent_sl) >= 2 and data[i]["close"] < recent_sl[-1][1]:
            data[i]["bos_bearish"] = True

        if len(recent_sl) >= 2 and recent_sl[-1][1] < recent_sl[-2][1]:
            if recent_sh and data[i]["close"] > recent_sh[-1][1]:
                data[i]["choch_bullish"] = True
        if len(recent_sh) >= 2 and recent_sh[-1][1] > recent_sh[-2][1]:
            if recent_sl and data[i]["close"] < recent_sl[-1][1]:
                data[i]["choch_bearish"] = True
    return data

def detect_liquidity_sweeps(data, swing_highs, swing_lows):
    """More sensitive sweep detection."""
    for i in range(1, len(data)):
        data[i]["liquidity_sweep_bullish"] = False
        data[i]["liquidity_sweep_bearish"] = False

        # Look at recent swing levels (last 200 bars)
        recent_lows = sorted([(sl[1], sl[0]) for sl in swing_lows if i - 200 < sl[0] < i])
        recent_highs = sorted([(sh[1], sh[0]) for sh in swing_highs if i - 200 < sh[0] < i], reverse=True)

        if recent_lows:
            lowest_low = recent_lows[0][0]
            # Sweep: price went below the low but closed above it (or wick below)
            if data[i]["low"] < lowest_low and data[i]["close"] > lowest_low:
                data[i]["liquidity_sweep_bullish"] = True
            # Also: price touches the level and reverses with momentum
            elif abs(data[i]["low"] - lowest_low) / lowest_low < 0.0005 and data[i]["close"] > data[i]["open"]:
                if data[i]["close"] - data[i]["open"] > (data[i]["high"] - data[i]["low"]) * 0.4:
                    data[i]["liquidity_sweep_bullish"] = True

        if recent_highs:
            highest_high = recent_highs[0][0]
            if data[i]["high"] > highest_high and data[i]["close"] < highest_high:
                data[i]["liquidity_sweep_bearish"] = True
            elif abs(data[i]["high"] - highest_high) / highest_high < 0.0005 and data[i]["close"] < data[i]["open"]:
                if data[i]["open"] - data[i]["close"] > (data[i]["high"] - data[i]["low"]) * 0.4:
                    data[i]["liquidity_sweep_bearish"] = True
    return data


# ── Backtest Engine ───────────────────────────────────────────────────────

class Trade:
    def __init__(self, entry_price, entry_date, direction, size=1.0):
        self.entry_price = entry_price
        self.entry_date = entry_date
        self.direction = direction
        self.size = size
        self.exit_price = None
        self.exit_date = None

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


def _resolve(operand, bar, prev_bar=None):
    if bar is None:
        return None
    operand = str(operand).strip().lower()
    if operand == "close": return bar.get("close")
    if operand == "open": return bar.get("open")
    if operand == "high": return bar.get("high")
    if operand == "low": return bar.get("low")
    if operand == "volume": return bar.get("volume")
    if operand == "position_bars_held": return bar.get("_position_bars_held")
    if operand in bar: return bar[operand]
    if operand == "upper_bb": return bar.get("bb_upper")
    if operand == "lower_bb": return bar.get("bb_lower")
    if operand == "middle_bb": return bar.get("bb_middle")
    try: return float(operand)
    except ValueError:
        if operand == "true": return 1.0
        if operand == "false": return 0.0
        return None


def _evaluate_condition(bar, prev_bar, cond):
    left = _resolve(cond.get("left_operand", ""), bar, prev_bar)
    right = _resolve(cond.get("right_operand", ""), bar, prev_bar)
    op = cond.get("operator", "==")
    if left is None or right is None: return False
    try: lv, rv = float(left), float(right)
    except (ValueError, TypeError): return False
    if op == ">": return lv > rv
    if op == "<": return lv < rv
    if op == "==": return abs(lv - rv) < 1e-10
    if op == ">=": return lv >= rv
    if op == "<=": return lv <= rv
    if op == "crosses_above":
        pl = _resolve(cond.get("left_operand", ""), prev_bar)
        pr = _resolve(cond.get("right_operand", ""), prev_bar)
        if pl is None or pr is None: return False
        return float(pl) <= float(pr) and lv > rv
    if op == "crosses_below":
        pl = _resolve(cond.get("left_operand", ""), prev_bar)
        pr = _resolve(cond.get("right_operand", ""), prev_bar)
        if pl is None or pr is None: return False
        return float(pl) >= float(pr) and lv < rv
    return False


def _check_signal(bar, prev_bar, signal):
    condition = signal.get("condition", {})
    logic = condition.get("logic", "AND")
    conditions = condition.get("conditions", [])
    results = [_evaluate_condition(bar, prev_bar, c) for c in conditions]
    if not results: return False
    return all(results) if logic == "AND" else any(results)


def _max_drawdown(equity_curve):
    if not equity_curve: return 0
    peak = equity_curve[0]
    max_dd = 0
    for eq in equity_curve:
        if eq > peak: peak = eq
        dd = (peak - eq) / peak if peak > 0 else 0
        if dd > max_dd: max_dd = dd
    return max_dd


def run_backtest(data, strategy, initial_capital=10000.0, commission=0.001):
    trades = []
    equity_curve = []
    position = None
    equity = initial_capital
    position_size = 1.0
    rm = strategy.get("risk_management", {})
    sl_pips = rm.get("stop_loss", 30)
    tp_pips = rm.get("take_profit", 60)
    trailing_pips = rm.get("trailing_stop", 0)
    highest_since_entry = 0
    bars_since_entry = 0

    # Convert pips to price (for EURUSD: 1 pip = 0.0001)
    pip_size = 0.0001
    sl_price = sl_pips * pip_size
    tp_price = tp_pips * pip_size
    trail_price = trailing_pips * pip_size

    entry_signals = strategy.get("entry_signals", [])
    exit_signals = strategy.get("exit_signals", [])

    for i in range(1, len(data)):
        bar = data[i]
        prev_bar = data[i - 1]
        bar["_position_bars_held"] = bars_since_entry if position else 0

        # ── Exits ──
        if position is not None:
            exit_reason = None
            exit_price = None

            if position["direction"] == "long":
                if sl_price and bar["low"] <= position["entry"] - sl_price:
                    exit_price = position["entry"] - sl_price
                    exit_reason = "sl"
                elif tp_price and bar["high"] >= position["entry"] + tp_price:
                    exit_price = position["entry"] + tp_price
                    exit_reason = "tp"
                elif trail_price:
                    highest_since_entry = max(highest_since_entry, bar["high"])
                    trail_level = highest_since_entry - trail_price
                    if bar["low"] <= trail_level:
                        exit_price = trail_level
                        exit_reason = "trail"
            else:
                if sl_price and bar["high"] >= position["entry"] + sl_price:
                    exit_price = position["entry"] + sl_price
                    exit_reason = "sl"
                elif tp_price and bar["low"] <= position["entry"] - tp_price:
                    exit_price = position["entry"] - tp_price
                    exit_reason = "tp"

            # Signal exits
            if exit_reason is None and exit_signals:
                for sig in exit_signals:
                    st = sig.get("type", "close_all")
                    if st == "close_long" and position["direction"] != "long": continue
                    if st == "close_short" and position["direction"] != "short": continue
                    if _check_signal(bar, prev_bar, sig):
                        exit_price = bar["open"]
                        exit_reason = "signal"
                        break

            if exit_reason:
                t = Trade(position["entry"], position["date"], position["direction"])
                t.exit_price = exit_price
                t.exit_date = bar["date"]
                pnl = t.pnl - (t.entry_price + exit_price) * commission * position_size
                equity += pnl
                trades.append(t)
                position = None
                highest_since_entry = 0
                bars_since_entry = 0

        # ── Entries ──
        if position is None and entry_signals:
            for sig in entry_signals:
                if _check_signal(bar, prev_bar, sig):
                    direction = "long" if sig.get("type") == "buy" else "short"
                    entry_price = bar["open"]
                    position = {"direction": direction, "entry": entry_price, "date": bar["date"]}
                    highest_since_entry = entry_price
                    bars_since_entry = 0
                    break

        if position:
            bars_since_entry += 1
        equity_curve.append(round(equity, 2))

    # Close open position
    if position is not None:
        t = Trade(position["entry"], position["date"], position["direction"])
        t.exit_price = data[-1]["close"]
        t.exit_date = data[-1]["date"]
        pnl = t.pnl - (t.entry_price + data[-1]["close"]) * commission * position_size
        equity += pnl
        trades.append(t)

    # Metrics
    if not trades:
        return {"total_return": 0, "sharpe_ratio": 0, "sortino_ratio": 0, "max_drawdown": 0,
                "win_rate": 0, "profit_factor": 0, "total_trades": 0, "net_profit": 0,
                "expectancy": 0, "omega_ratio": 0, "calmar_ratio": 0}

    returns = [t.return_pct for t in trades]
    wins = [t for t in trades if t.is_win]
    losses = [t for t in trades if t.is_loss]
    gross_profit = sum(t.pnl for t in wins) if wins else 0
    gross_loss = abs(sum(t.pnl for t in losses)) if losses else 0
    net_profit = gross_profit - gross_loss

    if equity_curve:
        total_return = (equity_curve[-1] - initial_capital) / initial_capital
    else:
        total_return = 0

    win_rate = len(wins) / len(trades) if trades else 0
    pf = gross_profit / gross_loss if gross_loss > 0 else 0

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
        gains_above = sum(r for r in returns if r > 0)
        losses_below = sum(-r for r in returns if r < 0)
        omega = gains_above / losses_below if losses_below > 0 else 0
    else:
        omega = 0

    return {
        "total_return": round(total_return * 100, 2) or 0.0,
        "sharpe_ratio": round(float(sharpe), 4) or 0.0,
        "sortino_ratio": round(float(sortino), 4) or 0.0,
        "max_drawdown": round(max_dd * 100, 2) or 0.0,
        "win_rate": round(win_rate * 100, 2) or 0.0,
        "profit_factor": round(float(pf), 4) or 0.0,
        "total_trades": len(trades),
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "net_profit": round(net_profit, 4),
        "expectancy": round(win_rate * (gross_profit / len(wins) if wins else 0) +
                            (1 - win_rate) * (-gross_loss / len(losses) if losses else 0), 4),
        "omega_ratio": round(float(omega), 4) or 0.0,
        "calmar_ratio": round(float(calmar), 4) or 0.0,
    }


# ── Strategy Variations ───────────────────────────────────────────────────

def get_variations():
    """Generate Smart Money Trap strategy variations with different parameters."""
    variations = []

    # Base configurations for different SL/TP combinations
    sl_tp_configs = [
        (20, 40), (25, 50), (30, 60), (35, 70), (40, 80),
        (30, 90), (40, 120), (50, 100), (25, 75), (35, 105),
    ]

    # ── Type 1: Sweep + CHoCH (classic) ──
    for sl, tp in sl_tp_configs:
        variations.append({
            "name": f"SMT_Sweep_CHoCH_SL{sl}TP{tp}",
            "description": f"Liquidity Sweep + CHoCH | SL:{sl} TP:{tp}",
            "entry_signals": [
                {"type": "buy", "condition": {"logic": "AND", "conditions": [
                    {"left_operand": "liquidity_sweep_bullish", "operator": "==", "right_operand": "true"},
                    {"left_operand": "choch_bullish", "operator": "==", "right_operand": "true"},
                ]}, "confidence": 0.85},
                {"type": "sell", "condition": {"logic": "AND", "conditions": [
                    {"left_operand": "liquidity_sweep_bearish", "operator": "==", "right_operand": "true"},
                    {"left_operand": "choch_bearish", "operator": "==", "right_operand": "true"},
                ]}, "confidence": 0.85},
            ],
            "exit_signals": [
                {"type": "close_long", "condition": {"logic": "OR", "conditions": [
                    {"left_operand": "choch_bearish", "operator": "==", "right_operand": "true"},
                    {"left_operand": "position_bars_held", "operator": ">", "right_operand": "20"},
                ]}, "confidence": 0.7},
                {"type": "close_short", "condition": {"logic": "OR", "conditions": [
                    {"left_operand": "choch_bullish", "operator": "==", "right_operand": "true"},
                    {"left_operand": "position_bars_held", "operator": ">", "right_operand": "20"},
                ]}, "confidence": 0.7},
            ],
            "risk_management": {"stop_loss": sl, "take_profit": tp},
        })

    # ── Type 2: Sweep + FVG ──
    for sl, tp in sl_tp_configs[:6]:
        variations.append({
            "name": f"SMT_Sweep_FVG_SL{sl}TP{tp}",
            "description": f"Liquidity Sweep + FVG entry | SL:{sl} TP:{tp}",
            "entry_signals": [
                {"type": "buy", "condition": {"logic": "AND", "conditions": [
                    {"left_operand": "liquidity_sweep_bullish", "operator": "==", "right_operand": "true"},
                    {"left_operand": "fvg_bullish", "operator": "==", "right_operand": "true"},
                ]}, "confidence": 0.8},
                {"type": "sell", "condition": {"logic": "AND", "conditions": [
                    {"left_operand": "liquidity_sweep_bearish", "operator": "==", "right_operand": "true"},
                    {"left_operand": "fvg_bearish", "operator": "==", "right_operand": "true"},
                ]}, "confidence": 0.8},
            ],
            "exit_signals": [
                {"type": "close_long", "condition": {"logic": "OR", "conditions": [
                    {"left_operand": "fvg_bearish", "operator": "==", "right_operand": "true"},
                    {"left_operand": "position_bars_held", "operator": ">", "right_operand": "25"},
                ]}, "confidence": 0.65},
                {"type": "close_short", "condition": {"logic": "OR", "conditions": [
                    {"left_operand": "fvg_bullish", "operator": "==", "right_operand": "true"},
                    {"left_operand": "position_bars_held", "operator": ">", "right_operand": "25"},
                ]}, "confidence": 0.65},
            ],
            "risk_management": {"stop_loss": sl, "take_profit": tp},
        })

    # ── Type 3: Sweep + Order Block ──
    for sl, tp in sl_tp_configs[:6]:
        variations.append({
            "name": f"SMT_Sweep_OB_SL{sl}TP{tp}",
            "description": f"Liquidity Sweep + Order Block | SL:{sl} TP:{tp}",
            "entry_signals": [
                {"type": "buy", "condition": {"logic": "AND", "conditions": [
                    {"left_operand": "liquidity_sweep_bullish", "operator": "==", "right_operand": "true"},
                    {"left_operand": "price_at_ob_bullish", "operator": "==", "right_operand": "true"},
                ]}, "confidence": 0.8},
                {"type": "sell", "condition": {"logic": "AND", "conditions": [
                    {"left_operand": "liquidity_sweep_bearish", "operator": "==", "right_operand": "true"},
                    {"left_operand": "price_at_ob_bearish", "operator": "==", "right_operand": "true"},
                ]}, "confidence": 0.8},
            ],
            "exit_signals": [
                {"type": "close_long", "condition": {"logic": "OR", "conditions": [
                    {"left_operand": "bos_bearish", "operator": "==", "right_operand": "true"},
                    {"left_operand": "position_bars_held", "operator": ">", "right_operand": "30"},
                ]}, "confidence": 0.65},
                {"type": "close_short", "condition": {"logic": "OR", "conditions": [
                    {"left_operand": "bos_bullish", "operator": "==", "right_operand": "true"},
                    {"left_operand": "position_bars_held", "operator": ">", "right_operand": "30"},
                ]}, "confidence": 0.65},
            ],
            "risk_management": {"stop_loss": sl, "take_profit": tp},
        })

    # ── Type 4: Sweep + RSI ──
    for sl, tp in [(25, 50), (30, 60), (35, 70), (40, 80), (30, 90)]:
        variations.append({
            "name": f"SMT_Sweep_RSI_SL{sl}TP{tp}",
            "description": f"Liquidity Sweep + RSI | SL:{sl} TP:{tp}",
            "entry_signals": [
                {"type": "buy", "condition": {"logic": "AND", "conditions": [
                    {"left_operand": "liquidity_sweep_bullish", "operator": "==", "right_operand": "true"},
                    {"left_operand": "rsi(14)", "operator": "<", "right_operand": "40"},
                ]}, "confidence": 0.75},
                {"type": "sell", "condition": {"logic": "AND", "conditions": [
                    {"left_operand": "liquidity_sweep_bearish", "operator": "==", "right_operand": "true"},
                    {"left_operand": "rsi(14)", "operator": ">", "right_operand": "60"},
                ]}, "confidence": 0.75},
            ],
            "exit_signals": [
                {"type": "close_long", "condition": {"logic": "OR", "conditions": [
                    {"left_operand": "rsi(14)", "operator": ">", "right_operand": "65"},
                    {"left_operand": "position_bars_held", "operator": ">", "right_operand": "20"},
                ]}, "confidence": 0.65},
                {"type": "close_short", "condition": {"logic": "OR", "conditions": [
                    {"left_operand": "rsi(14)", "operator": "<", "right_operand": "35"},
                    {"left_operand": "position_bars_held", "operator": ">", "right_operand": "20"},
                ]}, "confidence": 0.65},
            ],
            "risk_management": {"stop_loss": sl, "take_profit": tp},
        })

    # ── Type 5: Sweep + Bollinger ──
    for sl, tp in [(25, 50), (30, 60), (35, 70), (20, 40)]:
        variations.append({
            "name": f"SMT_Sweep_BB_SL{sl}TP{tp}",
            "description": f"Liquidity Sweep + Bollinger Band | SL:{sl} TP:{tp}",
            "entry_signals": [
                {"type": "buy", "condition": {"logic": "AND", "conditions": [
                    {"left_operand": "liquidity_sweep_bullish", "operator": "==", "right_operand": "true"},
                    {"left_operand": "close", "operator": "<", "right_operand": "bb_lower"},
                ]}, "confidence": 0.75},
                {"type": "sell", "condition": {"logic": "AND", "conditions": [
                    {"left_operand": "liquidity_sweep_bearish", "operator": "==", "right_operand": "true"},
                    {"left_operand": "close", "operator": ">", "right_operand": "bb_upper"},
                ]}, "confidence": 0.75},
            ],
            "exit_signals": [
                {"type": "close_long", "condition": {"logic": "OR", "conditions": [
                    {"left_operand": "close", "operator": ">", "right_operand": "bb_middle"},
                    {"left_operand": "position_bars_held", "operator": ">", "right_operand": "15"},
                ]}, "confidence": 0.65},
                {"type": "close_short", "condition": {"logic": "OR", "conditions": [
                    {"left_operand": "close", "operator": "<", "right_operand": "bb_middle"},
                    {"left_operand": "position_bars_held", "operator": ">", "right_operand": "15"},
                ]}, "confidence": 0.65},
            ],
            "risk_management": {"stop_loss": sl, "take_profit": tp},
        })

    # ── Type 6: Sweep + EMA Trend Filter ──
    for sl, tp in [(30, 60), (35, 70), (40, 80), (30, 90), (40, 120)]:
        variations.append({
            "name": f"SMT_Sweep_Trend_SL{sl}TP{tp}",
            "description": f"Liquidity Sweep + EMA Trend | SL:{sl} TP:{tp}",
            "entry_signals": [
                {"type": "buy", "condition": {"logic": "AND", "conditions": [
                    {"left_operand": "liquidity_sweep_bullish", "operator": "==", "right_operand": "true"},
                    {"left_operand": "close", "operator": ">", "right_operand": "ema(200)"},
                    {"left_operand": "ema(50)", "operator": ">", "right_operand": "ema(200)"},
                ]}, "confidence": 0.8},
                {"type": "sell", "condition": {"logic": "AND", "conditions": [
                    {"left_operand": "liquidity_sweep_bearish", "operator": "==", "right_operand": "true"},
                    {"left_operand": "close", "operator": "<", "right_operand": "ema(200)"},
                    {"left_operand": "ema(50)", "operator": "<", "right_operand": "ema(200)"},
                ]}, "confidence": 0.8},
            ],
            "exit_signals": [
                {"type": "close_long", "condition": {"logic": "OR", "conditions": [
                    {"left_operand": "close", "operator": "<", "right_operand": "ema(50)"},
                    {"left_operand": "position_bars_held", "operator": ">", "right_operand": "25"},
                ]}, "confidence": 0.65},
                {"type": "close_short", "condition": {"logic": "OR", "conditions": [
                    {"left_operand": "close", "operator": ">", "right_operand": "ema(50)"},
                    {"left_operand": "position_bars_held", "operator": ">", "right_operand": "25"},
                ]}, "confidence": 0.65},
            ],
            "risk_management": {"stop_loss": sl, "take_profit": tp},
        })

    return variations


def score_strategy(metrics):
    """Score strategy: balance return, consistency, and risk."""
    if metrics["total_trades"] < 5:
        return -999

    score = 0
    score += metrics["total_return"] * 3
    score += metrics["sharpe_ratio"] * 15
    score += metrics["sortino_ratio"] * 5
    score += metrics["win_rate"] * 0.5
    score += metrics["profit_factor"] * 8
    score += metrics["omega_ratio"] * 5
    score -= metrics["max_drawdown"] * 1.5
    score += metrics["net_profit"] * 2

    # Penalize too few trades
    if metrics["total_trades"] < 15:
        score *= 0.6
    elif metrics["total_trades"] < 30:
        score *= 0.85

    # Penalize extreme drawdown
    if metrics["max_drawdown"] > 3:
        score -= (metrics["max_drawdown"] - 3) * 5

    return score


def main():
    print("=" * 70)
    print("SMART MONEY TRAP - STRATEGY RESEARCH ENGINE")
    print("=" * 70)
    print()

    # Prepare data
    print("[1/4] Generating realistic data with stop-hunt patterns...")
    data = generate_realistic_data("EURUSD", n_bars=10000)
    print(f"  {len(data)} bars generated")

    # Calculate indicators
    print("[2/4] Computing indicators and ICT concepts...")
    data = calc_ema(data, 50)
    data = calc_ema(data, 200)
    data = calc_rsi(data, 14)
    data = calc_atr(data, 14)
    data = calc_bollinger(data, 20, 2.0)
    data = detect_fvg(data)
    data = detect_order_blocks(data)
    swing_highs, swing_lows = detect_swing_points(data, lookback=3)
    data = detect_bos_choch(data, swing_highs, swing_lows)
    data = detect_liquidity_sweeps(data, swing_highs, swing_lows)

    # Count detected concepts
    sweeps_bull = sum(1 for d in data if d.get("liquidity_sweep_bullish"))
    sweeps_bear = sum(1 for d in data if d.get("liquidity_sweep_bearish"))
    fvg_bull = sum(1 for d in data if d.get("fvg_bullish"))
    fvg_bear = sum(1 for d in data if d.get("fvg_bearish"))
    choch_bull = sum(1 for d in data if d.get("choch_bullish"))
    choch_bear = sum(1 for d in data if d.get("choch_bearish"))
    print(f"  Sweeps: {sweeps_bull} bull / {sweeps_bear} bear")
    print(f"  FVGs: {fvg_bull} bull / {fvg_bear} bear")
    print(f"  CHoCH: {choch_bull} bull / {choch_bear} bear")
    print()

    # Generate variations
    print("[3/4] Generating strategy variations...")
    variations = get_variations()
    print(f"  {len(variations)} variations")
    print()

    # Backtest all
    print("[4/4] Backtesting all variations...")
    print("-" * 70)
    results = []
    for i, strat in enumerate(variations):
        metrics = run_backtest(data, strat)
        score = score_strategy(metrics)
        results.append({"strategy": strat, "metrics": metrics, "score": score})
        if metrics["total_trades"] > 0:
            print(f"  [{i+1}/{len(variations)}] {strat['name']}: "
                  f"Ret={metrics['total_return']}% Sharpe={metrics['sharpe_ratio']} "
                  f"WR={metrics['win_rate']}% PF={metrics['profit_factor']} "
                  f"Trades={metrics['total_trades']} Score={score:.0f}")

    # Sort by score
    results.sort(key=lambda x: x["score"], reverse=True)

    # Filter valid results
    valid = [r for r in results if r["score"] > -999]

    print()
    print("=" * 70)
    print("TOP 10 STRATEGIES:")
    print("=" * 70)
    for rank, r in enumerate(valid[:10], 1):
        m = r["metrics"]
        marker = " <<< BEST" if rank == 1 else ""
        print(f"  #{rank} {r['strategy']['name']}{marker}")
        print(f"     Return: {m['total_return']}% | Sharpe: {m['sharpe_ratio']} | "
              f"MaxDD: {m['max_drawdown']}%")
        print(f"     WinRate: {m['win_rate']}% | PF: {m['profit_factor']} | "
              f"Omega: {m['omega_ratio']} | Trades: {m['total_trades']}")
        print(f"     Net: {m['net_profit']} | Score: {r['score']:.0f}")
        print()

    if valid:
        best = valid[0]
        print("=" * 70)
        print(f"BEST: {best['strategy']['name']}")
        print(f"Description: {best['strategy']['description']}")
        print(f"Score: {best['score']:.0f}")
        print()

        # Save results
        with open("/root/trading-strategy-ai-platform/smt_results.json", "w") as f:
            json.dump({
                "best_strategy": best["strategy"],
                "best_metrics": best["metrics"],
                "best_score": best["score"],
                "top_10": [{"name": r["strategy"]["name"], "score": r["score"], "metrics": r["metrics"]}
                           for r in valid[:10]],
            }, f, indent=2, default=str)
        print("Results saved to: /root/trading-strategy-ai-platform/smt_results.json")

        return best["strategy"], best["metrics"]
    else:
        print("No valid strategies found!")
        return None, None


if __name__ == "__main__":
    best_strat, best_metrics = main()
