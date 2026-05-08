"""
Trading Agent - LLM-first universal strategy engine.
The LLM understands ANY trading strategy and generates structured JSON via function calling.
All tools (backtest, mutate, MT5) are executed as LLM tool calls.
"""
from __future__ import annotations
import asyncio
import json
import os
from typing import List, Dict, Any, Optional

from strategy.parser import StrategyParser
from backtester.engine import BacktestEngine
from mutator.genetic import GeneticMutator
from mt5.generator import MT5Generator
from reports.generator import ReportGenerator


SYSTEM_PROMPT = """You are the world's most capable quantitative trading AI. You understand EVERY trading methodology ever invented:
- Classical technical analysis (any indicator, any combination)
- ICT / Smart Money Concepts (FVG, Order Block, BOS, CHoCH, CRT, Liquidity, Killzones, etc.)
- Price action (pin bars, engulfing, double top/bottom, head & shoulders, etc.)
- Statistical / quantitative (mean reversion, momentum, pairs trading, etc.)
- Options strategies (spreads, straddles, butterflies, etc.)
- ANY novel or hybrid strategy the user describes

Your workflow for EVERY user message:
1. UNDERSTAND the strategy deeply — ask clarifying questions if truly ambiguous
2. CALL parse_strategy with the complete structured strategy JSON
3. CALL run_backtest to test it on historical data
4. Optionally call mutate_strategy to evolve better variants
5. Optionally call generate_mt5 to create MQL5 code
6. Present the COMPLETE results: strategy summary, backtest metrics, trades

For parse_strategy, generate a COMPLETE strategy JSON with:
- name, type, instruments, timeframes
- indicators with specific parameters (periods, levels)
- entry_signals with precise conditions (left_operand, operator, right_operand)
- exit_signals (opposite conditions or time-based)
- risk management (stop_loss, take_profit, risk_per_trade)

CONDITION OPERANDS you can use (these work in the backtester):
- Price: "close", "open", "high", "low", "volume"
- Indicators: "sma(20)", "ema(50)", "rsi(14)", "macd_line", "macd_signal", "bb_upper", "bb_lower", "bb_middle", "atr(14)", "stoch_k(14)", "cci(20)", "adx(14)", "obv", "vwap"
- Patterns: "fvg_bullish", "fvg_bearish", "ob_bullish", "ob_bearish", "bos_bullish", "bos_bearish", "choch_bullish", "choch_bearish", "crt_bullish", "crt_bearish", "near_liquidity_high", "near_liquidity_low", "liquidity_sweep_bullish", "liquidity_sweep_bearish", "price_at_ob_bullish", "price_at_ob_bearish"
- Position: "position_bars_held"
- Comparison values: "30", "70", "true", "false", etc.
- Operators: ">", "<", "==", ">=", "<=", "crosses_above", "crosses_below"

Respond in the user's language. Be thorough and educational."""


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "parse_strategy",
            "description": "Create structured trading strategy from natural language. MUST be called FIRST.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Original user message"},
                    "strategy": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "description": {"type": "string"},
                            "type": {"type": "string", "enum": ["trend_following", "mean_reversion", "breakout", "scalping", "swing", "arbitrage", "options", "custom"]},
                            "instruments": {"type": "array", "items": {"type": "string"}},
                            "timeframes": {"type": "array", "items": {"type": "string", "enum": ["M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1"]}},
                            "indicators": {"type": "array", "items": {"type": "object", "properties": {
                                "type": {"type": "string"},
                                "parameters": {"type": "object"}
                            }}},
                            "entry_signals": {"type": "array", "items": {
                                "type": "object",
                                "properties": {
                                    "type": {"type": "string", "enum": ["buy", "sell"]},
                                    "condition": {"type": "object", "properties": {
                                        "logic": {"type": "string", "enum": ["AND", "OR"]},
                                        "conditions": {"type": "array", "items": {
                                            "type": "object",
                                            "properties": {
                                                "left_operand": {"type": "string"},
                                                "operator": {"type": "string"},
                                                "right_operand": {"type": "string"}
                                            }
                                        }}
                                    }},
                                    "confidence": {"type": "number"}
                                }
                            }},
                            "exit_signals": {"type": "array", "items": {
                                "type": "object",
                                "properties": {
                                    "type": {"type": "string", "enum": ["close_long", "close_short", "close_all"]},
                                    "condition": {"type": "object", "properties": {
                                        "logic": {"type": "string"},
                                        "conditions": {"type": "array"}
                                    }},
                                    "confidence": {"type": "number"}
                                }
                            }},
                            "risk_management": {"type": "object", "properties": {
                                "stop_loss": {"type": "number"},
                                "stop_loss_type": {"type": "string"},
                                "take_profit": {"type": "number"},
                                "take_profit_type": {"type": "string"},
                                "trailing_stop": {"type": "number"},
                                "risk_per_trade": {"type": "number"},
                                "max_position_size": {"type": "number"},
                                "max_drawdown_limit": {"type": "number"}
                            }}
                        },
                        "required": ["instruments", "entry_signals"],
                    }
                },
                "required": ["text", "strategy"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_backtest",
            "description": "Execute backtest on historical data. Call after parse_strategy.",
            "parameters": {
                "type": "object",
                "properties": {
                    "strategy": {"type": "object", "description": "Strategy object from parse_strategy"},
                    "symbol": {"type": "string"},
                    "timeframe": {"type": "string"},
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                },
                "required": ["strategy"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "mutate_strategy",
            "description": "Evolve strategy using genetic algorithms.",
            "parameters": {
                "type": "object",
                "properties": {
                    "strategy": {"type": "object"},
                    "population_size": {"type": "integer"},
                    "generations": {"type": "integer"},
                },
                "required": ["strategy"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_mt5",
            "description": "Generate MQL5 Expert Advisor code.",
            "parameters": {
                "type": "object",
                "properties": {"strategy": {"type": "object"}},
                "required": ["strategy"]
            }
        }
    }
]


class LLMClient:
    """Async OpenRouter client with streaming support."""

    def __init__(self):
        self.api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENROUTER_TOKEN") or ""
        self.model = os.environ.get("OPENROUTER_MODEL", "openrouter/owl-alpha")
        self.base_url = "https://openrouter.ai/api/v1"
        self.available = bool(self.api_key)

    async def chat(self, messages: List[Dict], tools: Optional[List[Dict]] = None, max_tokens: int = 8000) -> Dict:
        if not self.available:
            return {"choices": [{"message": {"content": "LLM unavailable", "tool_calls": []}}]}
        import urllib.request, urllib.error
        payload = {"model": self.model, "messages": messages, "max_tokens": max_tokens}
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        data = json.dumps(payload).encode()
        req = urllib.request.Request(f"{self.base_url}/chat/completions", data=data, headers={
            "Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/crazycompanyinc/trading-strategy-ai-platform",
            "X-Title": "Trading Strategy AI Platform"}, method="POST")
        try:
            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=180))
            return json.loads(resp.read().decode())
        except Exception as e:
            return {"error": True, "message": str(e),
                    "choices": [{"message": {"content": f"LLM error: {e}", "tool_calls": []}}]}

    @staticmethod
    def extract_content(resp: Dict) -> str:
        try:
            return resp["choices"][0]["message"].get("content") or ""
        except (KeyError, IndexError):
            return ""

    @staticmethod
    def extract_tool_calls(resp: Dict) -> List[Dict]:
        try:
            return resp["choices"][0]["message"].get("tool_calls", [])
        except (KeyError, IndexError):
            return []


class TradingAgent:
    """Universal trading agent — LLM via function calling handles everything."""

    def __init__(self):
        self.llm = LLMClient()
        self.backtester = BacktestEngine()
        self.mutator = GeneticMutator()
        self.mt5_gen = MT5Generator()
        self.report_gen = ReportGenerator()
        print(f"[TradingAgent] LLM: {self.llm.available} ({self.llm.model})")

    async def process_message(self, message: str, images: List[str], session: str, sessions: Dict) -> Dict[str, Any]:
        result = {"response": "", "strategy": None, "backtest_results": None,
                  "mt5_code": None, "mutation_results": None, "robustness_results": None}

        # Build conversation
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if session in sessions:
            for msg in sessions[session].get("history", [])[-10:]:
                if msg.get("role") in ("user", "assistant"):
                    messages.append({"role": msg["role"], "content": msg["content"]})

        user_msg = message + (f"\n[{len(images)} images]" if images else "")
        messages.append({"role": "user", "content": user_msg})

        # ── Tool execution loop ──
        strategy_dict = None
        backtest_results = None
        mt5_code = None
        mutation_results = None
        llm_text = ""

        for iteration in range(8):  # max 8 tool calls
            resp = await self.llm.chat(messages, tools=TOOLS)
            if "error" in resp:
                print(f"[Agent] LLM error: {resp.get('message')}")

            tool_calls = self.llm.extract_tool_calls(resp)
            llm_text = self.llm.extract_content(resp)

            if not tool_calls:
                break  # LLM done

            messages.append({"role": "assistant", "content": llm_text, "tool_calls": tool_calls})

            for tc in tool_calls:
                func = tc.get("function", {})
                name = func.get("name", "")
                try:
                    args = json.loads(func.get("arguments", "{}"))
                except json.JSONDecodeError:
                    args = {}

                tool_result = {}
                print(f"[Agent] Tool: {name}")

                if name == "parse_strategy":
                    strategy_dict = self._ensure_strategy(args.get("strategy", {}), message)
                    tool_result = {"strategy": strategy_dict,
                                   "summary": f"Strategy: {strategy_dict.get('name')} | Indicators: {len(strategy_dict.get('indicators',[]))} | Entries: {len(strategy_dict.get('entry_signals',[]))} | Exits: {len(strategy_dict.get('exit_signals',[]))}"}

                elif name == "run_backtest":
                    strat = args.get("strategy") or strategy_dict
                    if strat:
                        symbol = args.get("symbol", strat.get("instruments", ["EURUSD"])[0])
                        tf = args.get("timeframe", "H1")
                        backtest_results = await asyncio.get_event_loop().run_in_executor(
                            None, lambda: self.backtester.run(
                                strategy=strat, symbol=symbol, timeframe=tf,
                                start_date=args.get("start_date", "2022-01-01"),
                                end_date=args.get("end_date", "2024-01-01")))
                        m = backtest_results.get("metrics", {})
                        tool_result = {
                            "total_trades": m.get("total_trades"), "total_return": m.get("total_return"),
                            "sharpe_ratio": m.get("sharpe_ratio"), "max_drawdown": m.get("max_drawdown"),
                            "win_rate": m.get("win_rate"), "profit_factor": m.get("profit_factor"),
                            "final_equity": backtest_results.get("final_equity")}

                elif name == "generate_mt5":
                    strat = args.get("strategy") or strategy_dict
                    if strat:
                        mt5_code = await asyncio.get_event_loop().run_in_executor(
                            None, lambda: self.mt5_gen.generate(strat))
                        tool_result = {"code_length": len(mt5_code)}

                elif name == "mutate_strategy":
                    strat = args.get("strategy") or strategy_dict
                    if strat:
                        mutation_results = await asyncio.get_event_loop().run_in_executor(
                            None, lambda: self.mutator.evolve(
                                base_strategy=strat,
                                population_size=args.get("population_size", 15),
                                generations=args.get("generations", 5)))
                        best = mutation_results.get("best_strategies", [])
                        tool_result = {
                            "evaluated": mutation_results.get("total_evaluated"),
                            "generations": mutation_results.get("generations_run"),
                            "best_sharpe": best[0]["metrics"].get("sharpe_ratio") if best else None}

                messages.append({"role": "tool", "tool_call_id": tc.get("id", f"tc_{iteration}"),
                                 "content": json.dumps(tool_result)})

        # ── Build final response ──
        parts = []
        if llm_text and "LLM error" not in llm_text and "LLM unavailable" not in llm_text:
            parts.append(llm_text)
        elif strategy_dict:
            parts.append(f"## Strategy: {strategy_dict.get('name', 'Custom')}")
            parts.append(f"Type: {strategy_dict.get('type')} | Instruments: {', '.join(strategy_dict.get('instruments', []))}")
            parts.append(f"Indicators: {len(strategy_dict.get('indicators', []))} | Entry signals: {len(strategy_dict.get('entry_signals', []))}")

        if backtest_results:
            m = backtest_results.get("metrics", {})
            parts.append("\n## Backtest Results")
            for label, key, suffix in [
                ("Total Return", "total_return", "%"), ("Sharpe Ratio", "sharpe_ratio", ""),
                ("Max Drawdown", "max_drawdown", "%"), ("Win Rate", "win_rate", "%"),
                ("Profit Factor", "profit_factor", ""), ("Total Trades", "total_trades", ""),
            ]:
                v = m.get(key)
                if v is not None:
                    parts.append(f"  - {label}: {v:.2f}{suffix}" if isinstance(v, float) else f"  - {label}: {v}{suffix}")

        if mutation_results:
            best = mutation_results.get("best_strategies", [])
            parts.append(f"\n## Genetic Evolution")
            parts.append(f"  Evaluated: {mutation_results.get('total_evaluated')} | Generations: {mutation_results.get('generations_run')}")
            if best:
                bm = best[0].get("metrics", {})
                parts.append(f"  Best Sharpe: {bm.get('sharpe_ratio', 0):.2f} | Best Return: {bm.get('total_return', 0):.1f}%")

        if mt5_code:
            parts.append(f"\n## MQL5 Code ({len(mt5_code)} chars)")
            parts.append(f"```mql5\n{mt5_code[:1500]}...\n```")

        result["response"] = "\n".join(parts) if parts else "Strategy processed successfully."
        result["strategy"] = strategy_dict
        result["backtest_results"] = backtest_results
        result["mt5_code"] = mt5_code
        result["mutation_results"] = mutation_results
        return result

    def _ensure_strategy(self, strat: dict, original: str) -> dict:
        """Normalize LLM-generated strategy, fill gaps from local parser if needed."""
        # If LLM gave us a complete strategy, use it
        if strat.get("instruments") and strat.get("entry_signals"):
            return {
                "name": strat.get("name", original[:50]),
                "description": strat.get("description", original[:500]),
                "type": strat.get("type", "custom"),
                "instruments": strat.get("instruments", ["EURUSD"]),
                "timeframes": strat.get("timeframes", ["H1"]),
                "indicators": strat.get("indicators", []),
                "entry_signals": strat.get("entry_signals", []),
                "exit_signals": strat.get("exit_signals", []),
                "risk_management": strat.get("risk_management", {"stop_loss": 50, "take_profit": 100}),
                "source_idea": original[:1000],
            }

        # Fallback: local parser
        print("[Agent] Using local parser fallback")
        try:
            local = StrategyParser()
            ir = local.parse(original)
            return ir.to_dict()
        except Exception as e:
            print(f"[Agent] Local parser error: {e}")
            return {
                "name": original[:50], "description": original[:500], "type": "custom",
                "instruments": ["EURUSD"], "timeframes": ["H1"], "indicators": [],
                "entry_signals": [], "exit_signals": [],
                "risk_management": {"stop_loss": 50, "take_profit": 100},
                "source_idea": original[:1000],
            }
