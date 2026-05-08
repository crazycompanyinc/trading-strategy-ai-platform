"""
Trading Agent - Universal strategy parser using LLM function calling.
The LLM generates structured strategy JSON for ANY trading concept —
not just predefined keywords. Works for ICT, price action, classical,
or any invented strategy.
"""
from __future__ import annotations
import asyncio
import json
import os
from typing import List, Dict, Any, Optional
from datetime import datetime

from strategy.parser import StrategyParser
from strategy.models import StrategyIR, IndicatorType
from backtester.engine import BacktestEngine
from mutator.genetic import GeneticMutator
from mt5.generator import MT5Generator
from reports.generator import ReportGenerator


SYSTEM_PROMPT = """You are a world-class quantitative trading expert. You understand ALL trading methodologies:
- Classical: trend following, mean reversion, breakout, scalping, swing
- ICT/Smart Money: FVG, Order Block, BOS, CHoCH, Liquidity, Killzones, OTE, CE
- Price action: pin bars, engulfing, inside bars, support/resistance
- Indicators: SMA, EMA, RSI, MACD, Bollinger, ATR, Stochastic, CCI, ADX, VWAP, OBV, MFI, etc.
- ANY invented or hybrid strategy the user describes

Your job is to:
1. UNDERSTAND the user's trading idea deeply — no matter how vague or novel
2. GENERATE a precise, backtestable strategy with specific rules
3. EXECUTE tools: parse_strategy, run_backtest, mutate_strategy, generate_mt5, run_robustness

CRITICAL RULES:
- ALWAYS call parse_strategy first to create the structured strategy
- ALWAYS call run_backtest after to test on historical data
- For vague ideas, make reasonable assumptions and state them
- Be specific with numeric parameters (periods, levels, thresholds)
- Include risk management (stop loss, take profit) even if not mentioned
- Respond in the same language as the user

When calling parse_strategy, provide a detailed JSON strategy object.
When calling run_backtest, use the returned strategy object directly."""


STRATEGY_SCHEMA = {
    "type": "object",
    "description": "Complete trading strategy specification for backtesting",
    "properties": {
        "name": {"type": "string", "description": "Short strategy name (max 50 chars)"},
        "description": {"type": "string", "description": "Strategy description"},
        "type": {"type": "string", "enum": ["trend_following", "mean_reversion", "breakout", "scalping", "swing", "arbitrage", "options", "custom"]},
        "instruments": {"type": "array", "items": {"type": "string"}, "description": "Trading instruments, e.g. [\"EURUSD\", \"GBPUSD\"]"},
        "timeframes": {"type": "array", "items": {"type": "string", "enum": ["M1","M5","M15","M30","H1","H4","D1","W1"]}, "description": "Timeframes"},
        "indicators": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "description": "Indicator type: sma, ema, rsi, macd, bollinger_bands, atr, stochastic, cci, adx, obv, vwap, volume, williams_r, mfi, donchian_channel, keltner_channel, ichimoku, supertrend, custom, ict_fvg, ict_order_block, ict_bos, ict_choch, ict_liquidity"},
                    "parameters": {"type": "object", "description": "Indicator parameters, e.g. {\"period\": 20} or {\"ict_concept\": \"ict_fvg\", \"direction\": \"both\"}"}
                }
            }
        },
        "entry_signals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["buy", "sell"]},
                    "condition": {
                        "type": "object",
                        "properties": {
                            "logic": {"type": "string", "enum": ["AND", "OR"]},
                            "conditions": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "left_operand": {"type": "string", "description": "e.g. \"close\", \"rsi(14)\", \"ict_fvg_bullish\", \"price_at_order_block_bullish\""},
                                        "operator": {"type": "string", "enum": [">", "<", "==", ">=", "<=", "crosses_above", "crosses_below"]},
                                        "right_operand": {"type": "string", "description": "e.g. \"sma(20)\", \"30\", \"true\""}
                                    }
                                }
                            }
                        }
                    },
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1}
                }
            }
        },
        "exit_signals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["close_long", "close_short", "close_all"]},
                    "condition": {
                        "type": "object",
                        "properties": {
                            "logic": {"type": "string", "enum": ["AND", "OR"]},
                            "conditions": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "left_operand": {"type": "string"},
                                        "operator": {"type": "string"},
                                        "right_operand": {"type": "string"}
                                    }
                                }
                            }
                        }
                    },
                    "confidence": {"type": "number"}
                }
            }
        },
        "risk_management": {
            "type": "object",
            "properties": {
                "stop_loss": {"type": "number", "description": "Stop loss in price units"},
                "stop_loss_type": {"type": "string", "enum": ["fixed", "atr_based", "percentage"]},
                "take_profit": {"type": "number", "description": "Take profit in price units"},
                "take_profit_type": {"type": "string", "enum": ["fixed", "atr_based", "percentage"]},
                "trailing_stop": {"type": "number"},
                "trailing_stop_type": {"type": "string", "enum": ["fixed", "atr_based"]},
                "risk_per_trade": {"type": "number", "description": "Percentage of equity per trade"},
                "max_position_size": {"type": "number", "description": "Max position size in lots"},
                "max_drawdown_limit": {"type": "number", "description": "Max drawdown percentage"},
                "max_open_positions": {"type": "integer"},
                "max_daily_trades": {"type": "integer"}
            }
        }
    }
}


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "parse_strategy",
            "description": "Create a structured, backtestable trading strategy from natural language. Use this FIRST for ANY trading idea.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "The user's natural language trading idea"},
                    "strategy": STRATEGY_SCHEMA,
                },
                "required": ["text", "strategy"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_backtest",
            "description": "Run backtest on historical data. ALWAYS call this after parse_strategy.",
            "parameters": {
                "type": "object",
                "properties": {
                    "strategy": {"type": "object", "description": "The strategy object from parse_strategy"},
                    "symbol": {"type": "string", "description": "Trading symbol"},
                    "timeframe": {"type": "string", "description": "Timeframe"},
                },
                "required": ["strategy"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mutate_strategy",
            "description": "Evolve strategy using genetic algorithms to find better variants.",
            "parameters": {
                "type": "object",
                "properties": {
                    "strategy": {"type": "object", "description": "Base strategy to mutate"},
                    "population_size": {"type": "integer", "default": 15},
                    "generations": {"type": "integer", "default": 5},
                },
                "required": ["strategy"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_mt5",
            "description": "Generate MQL5 Expert Advisor code from strategy.",
            "parameters": {
                "type": "object",
                "properties": {
                    "strategy": {"type": "object", "description": "Strategy to convert to MQL5"},
                },
                "required": ["strategy"],
            },
        },
    },
]


class OpenRouterClient:
    """Async OpenRouter client."""

    def __init__(self):
        self.api_key = (
            os.environ.get("OPENROUTER_API_KEY")
            or os.environ.get("OPENROUTER_TOKEN")
            or ""
        )
        self.model = os.environ.get("OPENROUTER_MODEL", "openrouter/owl-alpha")
        self.base_url = "https://openrouter.ai/api/v1"
        self.use_llm = bool(self.api_key)

    async def chat(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict]] = None,
        max_tokens: int = 8000,
    ) -> Dict[str, Any]:
        if not self.use_llm:
            return {"choices": [{"message": {"content": "LLM not available. Using local parser.", "tool_calls": []}}]}

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        import urllib.request
        import urllib.error

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/crazycompanyinc/trading-strategy-ai-platform",
                "X-Title": "Trading Strategy AI Platform",
            },
            method="POST",
        )

        try:
            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=180))
            return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            return {
                "error": True,
                "message": str(e),
                "choices": [{"message": {"content": f"LLM error: {e}", "tool_calls": []}}],
            }

    def extract_content(self, response: Dict) -> str:
        try:
            return response["choices"][0]["message"].get("content") or ""
        except (KeyError, IndexError):
            return ""

    def extract_tool_calls(self, response: Dict) -> List[Dict]:
        try:
            return response["choices"][0]["message"].get("tool_calls", [])
        except (KeyError, IndexError):
            return []


class TradingAgent:
    """
    Universal trading agent. Uses LLM to parse ANY trading idea into
    a structured, backtestable strategy. The LLM is the primary parser;
    local keyword matching is only a fallback.
    """

    def __init__(self):
        self.llm = OpenRouterClient()
        self.backtester = BacktestEngine()
        self.mutator = GeneticMutator()
        self.mt5_gen = MT5Generator()
        self.report_gen = ReportGenerator()
        print(f"[TradingAgent] LLM connected: {self.llm.use_llm}, model: {self.llm.model}")

    async def process_message(
        self,
        message: str,
        images: List[str],
        session: str,
        sessions: Dict[str, dict],
    ) -> Dict[str, Any]:
        result = {
            "response": "",
            "strategy": None,
            "backtest_results": None,
            "mt5_code": None,
            "mutation_results": None,
            "robustness_results": None,
        }

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if session in sessions:
            for msg in sessions[session].get("history", [])[-10:]:
                if msg.get("role") in ("user", "assistant"):
                    messages.append({"role": msg["role"], "content": msg["content"]})

        user_content = message
        if images:
            user_content += f"\n[{len(images)} image(s) uploaded]"
        messages.append({"role": "user", "content": user_content})

        # Tool execution loop
        strategy_dict = None
        backtest_results = None
        mt5_code = None
        mutation_results = None
        llm_content = ""
        max_iterations = 5

        for iteration in range(max_iterations):
            llm_response = await self.llm.chat(messages, tools=TOOLS)

            if "error" in llm_response:
                print(f"[TradingAgent] LLM error: {llm_response.get('message')}")

            tool_calls = self.llm.extract_tool_calls(llm_response)
            llm_content = self.llm.extract_content(llm_response)

            if not tool_calls:
                break

            # Add assistant message with tool calls
            assistant_msg = {"role": "assistant", "content": llm_content}
            if tool_calls:
                assistant_msg["tool_calls"] = tool_calls
            messages.append(assistant_msg)

            for tc in tool_calls:
                func = tc.get("function", {})
                func_name = func.get("name", "")
                try:
                    args = json.loads(func.get("arguments", "{}"))
                except json.JSONDecodeError:
                    args = {}

                print(f"[TradingAgent] Executing: {func_name}")
                tool_result = {}

                if func_name == "parse_strategy":
                    # Accept the LLM-generated strategy directly
                    llm_strategy = args.get("strategy", {})
                    if llm_strategy:
                        strategy_dict = self._normalize_strategy(llm_strategy, message)
                    else:
                        # Fallback to local parser
                        from strategy.parser import StrategyParser
                        local = StrategyParser()
                        ir = local.parse(message)
                        strategy_dict = ir.to_dict()
                    
                    tool_result = {
                        "strategy": strategy_dict,
                        "summary": self._strategy_summary(strategy_dict),
                    }

                elif func_name == "run_backtest":
                    strat = args.get("strategy") or strategy_dict
                    if strat:
                        symbol = args.get("symbol", strat.get("instruments", ["EURUSD"])[0] if strat.get("instruments") else "EURUSD")
                        timeframe = args.get("timeframe", "H1")
                        backtest_results = await asyncio.get_event_loop().run_in_executor(
                            None,
                            lambda: self.backtester.run(strategy=strat, symbol=symbol, timeframe=timeframe),
                        )
                        metrics = backtest_results.get("metrics", {})
                        tool_result = {
                            "total_return": metrics.get("total_return"),
                            "sharpe_ratio": metrics.get("sharpe_ratio"),
                            "max_drawdown": metrics.get("max_drawdown"),
                            "win_rate": metrics.get("win_rate"),
                            "profit_factor": metrics.get("profit_factor"),
                            "total_trades": metrics.get("total_trades"),
                            "n_bars": backtest_results.get("n_bars"),
                            "final_equity": backtest_results.get("final_equity"),
                        }

                elif func_name == "generate_mt5":
                    strat = args.get("strategy") or strategy_dict
                    if strat:
                        mt5_code = await asyncio.get_event_loop().run_in_executor(
                            None, lambda: self.mt5_gen.generate(strat)
                        )
                        tool_result = {"code_length": len(mt5_code), "preview": mt5_code[:500]}

                elif func_name == "mutate_strategy":
                    strat = args.get("strategy") or strategy_dict
                    if strat:
                        mutation_results = await asyncio.get_event_loop().run_in_executor(
                            None,
                            lambda: self.mutator.evolve(
                                base_strategy=strat,
                                population_size=args.get("population_size", 15),
                                generations=args.get("generations", 5),
                            )
                        )
                        best = mutation_results.get("best_strategies", [])
                        tool_result = {
                            "total_evaluated": mutation_results.get("total_evaluated"),
                            "generations": mutation_results.get("generations_run"),
                            "best_sharpe": best[0]["metrics"].get("sharpe_ratio") if best else None,
                        }

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", f"call_{iteration}"),
                    "content": json.dumps(tool_result),
                })

        # Build response
        parts = []
        if llm_content and not llm_content.startswith("LLM error"):
            parts.append(llm_content)
        else:
            if strategy_dict:
                parts.append(f"## Strategy: {strategy_dict.get('name', 'Custom')}")
                parts.append(f"Type: {strategy_dict.get('type', 'custom')}")
        
        if backtest_results:
            metrics = backtest_results.get("metrics", {})
            parts.append("\n## Backtest Results")
            key_metrics = [
                ("Total Return", "total_return", "%"),
                ("Sharpe Ratio", "sharpe_ratio", ""),
                ("Max Drawdown", "max_drawdown", "%"),
                ("Win Rate", "win_rate", "%"),
                ("Profit Factor", "profit_factor", ""),
                ("Total Trades", "total_trades", ""),
            ]
            for label, key, suffix in key_metrics:
                val = metrics.get(key)
                if val is not None:
                    if isinstance(val, float):
                        parts.append(f"  - {label}: {val:.2f}{suffix}")
                    else:
                        parts.append(f"  - {label}: {val}{suffix}")

        if mutation_results:
            evo = mutation_results
            parts.append(f"\n## Genetic Evolution")
            parts.append(f"  - Strategies evaluated: {evo.get('total_evaluated', 0)}")
            best = evo.get("best_strategies", [])
            if best:
                bm = best[0].get("metrics", {})
                parts.append(f"  - Best Sharpe: {bm.get('sharpe_ratio', 0):.2f}")

        if mt5_code:
            parts.append(f"\n## MQL5 Code ({len(mt5_code)} chars)")
            parts.append(f"```mql5\n{mt5_code[:1500]}...\n```")

        result["response"] = "\n".join(parts) if parts else "Strategy processed."
        result["strategy"] = strategy_dict
        result["backtest_results"] = backtest_results
        result["mt5_code"] = mt5_code
        result["mutation_results"] = mutation_results

        return result

    def _normalize_strategy(self, llm_strategy: dict, original_text: str) -> dict:
        """Normalize the LLM-generated strategy dict to ensure consistency."""
        normalized = {
            "name": llm_strategy.get("name", original_text[:50]),
            "description": llm_strategy.get("description", original_text[:500]),
            "type": llm_strategy.get("type", "custom"),
            "instruments": llm_strategy.get("instruments", ["EURUSD"]),
            "timeframes": llm_strategy.get("timeframes", ["H1"]),
            "indicators": llm_strategy.get("indicators", []),
            "entry_signals": llm_strategy.get("entry_signals", []),
            "exit_signals": llm_strategy.get("exit_signals", []),
            "risk_management": llm_strategy.get("risk_management", {}),
            "tags": llm_strategy.get("tags", []),
            "source_idea": original_text[:1000],
        }
        
        # Ensure risk management has defaults if missing entirely
        if not normalized["risk_management"]:
            normalized["risk_management"] = {"stop_loss": 50, "take_profit": 100}
        
        # Ensure at least one entry signal exists
        if not normalized["entry_signals"]:
            direction = "buy"
            text_lower = original_text.lower()
            if any(kw in text_lower for kw in ["sell", "short", "vender", "venta", "bajista", "bearish"]):
                direction = "sell"
            normalized["entry_signals"] = [{
                "type": direction,
                "condition": {
                    "logic": "AND",
                    "conditions": [{
                        "left_operand": "close",
                        "operator": "crosses_above" if direction == "buy" else "crosses_below",
                        "right_operand": "sma(20)"
                    }]
                },
                "confidence": 0.6,
            }]
            # Add a default SMA indicator
            if not normalized["indicators"]:
                normalized["indicators"] = [{"type": "sma", "parameters": {"period": 20}}]
        
        return normalized

    def _strategy_summary(self, strategy: dict) -> str:
        parts = [
            f"Strategy: {strategy.get('name', 'Custom')}",
            f"Type: {strategy.get('type', 'custom')}",
            f"Instruments: {', '.join(strategy.get('instruments', ['EURUSD']))}",
            f"Timeframes: {', '.join(strategy.get('timeframes', ['H1']))}",
            f"Indicators: {len(strategy.get('indicators', []))}",
            f"Entry signals: {len(strategy.get('entry_signals', []))}",
            f"Exit signals: {len(strategy.get('exit_signals', []))}",
        ]
        return "\n".join(parts)
