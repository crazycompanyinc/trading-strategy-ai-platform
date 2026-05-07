"""
Trading Agent - NLP-powered agent connected to OpenRouter LLM.
Understands trading ideas via AI, parses them into structured strategies,
runs backtests, and generates MT5 code.
"""
from __future__ import annotations
import asyncio
import json
import os
import base64
import tempfile
from typing import List, Dict, Optional, Any
from datetime import datetime
import urllib.request
import urllib.error

from strategy.parser import StrategyParser
from strategy.models import StrategyIR, StrategyType, SignalType, ConditionOperator, ConditionGroup
from backtester.engine import BacktestEngine
from mt5.generator import MT5Generator
from reports.generator import ReportGenerator


SYSTEM_PROMPT = """You are an expert quantitative trading analyst and strategy developer. Your role is to:

1. **Understand** the user's trading idea deeply, no matter how vague or complex
2. **Research** concepts, indicators, or strategies mentioned
3. **Ask** clarifying questions when the idea is ambiguous
4. **Synthesize** a clear, actionable trading strategy with specific rules
5. **Explain** the strategy: instruments, timeframes, indicators, entry/exit rules, risk management
6. **Generate** structured strategy data for backtesting via the parse_strategy tool
7. **Run backtests** when the user wants via the run_backtest tool
8. **Generate MT5 code** via the generate_mt5 tool
9. **Run mutations** via the mutate_strategy tool to evolve strategies
10. **Run robustness tests** via the run_robustness tool

When analyzing images (charts, screenshots, hand-drawn diagrams):
- Identify chart patterns, indicators, support/resistance levels
- Extract any visible trading rules or setups

Be precise with parameters. If the user says "fast EMA", suggest period 9 or 12.
If they say "oversold RSI", use standard 30 level unless specified.

Available instruments: EURUSD, GBPUSD, USDJPY, USDCHF, AUDUSD, USDCAD, NZDUSD, XAUUSD, BTCUSD
Available timeframes: M1, M5, M15, M30, H1, H4, D1, W1
Available indicators: sma, ema, wma, rsi, macd, bollinger_bands, atr, stochastic, cci, adx, obv, vwap

Respond in the same language the user writes in. Be thorough and educational.
Always use the parse_strategy tool to create structured strategies from user descriptions.
"""


class OpenRouterClient:
    """Client for OpenRouter API - compatible with Hermes agent setup."""

    def __init__(self):
        self.api_key = (
            os.environ.get("OPENROUTER_API_KEY")
            or os.environ.get("OPENROUTER_TOKEN")
            or ""
        )
        self.model = (
            os.environ.get("OPENROUTER_MODEL")
            or "openrouter/owl-alpha"
        )
        self.base_url = "https://openrouter.ai/api/v1"
        self.use_llm = bool(self.api_key)

    async def chat(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict]] = None,
        tool_choice: str = "auto",
    ) -> Dict[str, Any]:
        """Send a chat completion request to OpenRouter."""
        if not self.use_llm:
            return {
                "choices": [{
                    "message": {
                        "content": None,
                        "tool_calls": [{
                            "id": "call_fallback",
                            "function": {
                                "name": "parse_strategy",
                                "arguments": json.dumps({"text": messages[-1].get("content", "")})
                            }
                        }]
                    }
                }]
            }

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice

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
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            return {
                "error": True,
                "status_code": e.code,
                "message": error_body[:500],
                "choices": [{
                    "message": {
                        "content": f"LLM API error ({e.code}): {error_body[:200]}. Falling back to basic parsing."
                    }
                }]
            }
        except Exception as e:
            return {
                "error": True,
                "message": str(e),
                "choices": [{
                    "message": {
                        "content": f"LLM connection error: {e}. Falling back to basic parsing."
                    }
                }]
            }

    def extract_content(self, response: Dict) -> str:
        """Extract text content from LLM response."""
        try:
            msg = response["choices"][0]["message"]
            content = msg.get("content")
            if content:
                return content
            # Check for tool_calls
            tool_calls = msg.get("tool_calls", [])
            if tool_calls:
                return json.dumps({"tool_calls": tool_calls})
            return str(msg)
        except (KeyError, IndexError):
            return ""

    def extract_tool_calls(self, response: Dict) -> List[Dict]:
        """Extract tool calls from LLM response."""
        try:
            msg = response["choices"][0]["message"]
            return msg.get("tool_calls", [])
        except (KeyError, IndexError):
            return []


# Tool definitions for function calling
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "parse_strategy",
            "description": "Parse a natural language trading idea into a structured strategy. Use this ALWAYS when the user describes a trading idea.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The user's natural language description of their trading idea"
                    }
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_backtest",
            "description": "Run a backtest for a given strategy. Use when user wants to test a strategy on historical data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "strategy": {"type": "object", "description": "The strategy object to backtest"},
                    "symbol": {"type": "string", "description": "Trading symbol, default EURUSD"},
                    "timeframe": {"type": "string", "description": "Timeframe, default H1"}
                },
                "required": ["strategy"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_mt5",
            "description": "Generate MQL5 Expert Advisor code from a strategy. Use when user wants MT5/MQL5 code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "strategy": {"type": "object", "description": "The strategy to convert to MQL5"}
                },
                "required": ["strategy"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "mutate_strategy",
            "description": "Evolve a strategy using genetic algorithms to find better variants. Use when user wants to optimize/evolve a strategy.",
            "parameters": {
                "type": "object",
                "properties": {
                    "strategy": {"type": "object", "description": "Base strategy to mutate"},
                    "population_size": {"type": "integer", "description": "Population size, default 20"},
                    "generations": {"type": "integer", "description": "Number of generations, default 10"},
                    "objectives": {"type": "array", "items": {"type": "string"}, "description": "Objectives to optimize, default [\"sharpe\", \"profit_factor\"]"}
                },
                "required": ["strategy"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_robustness",
            "description": "Run robustness tests (Monte Carlo, walk-forward, sensitivity). Use when user wants to test strategy robustness.",
            "parameters": {
                "type": "object",
                "properties": {
                    "strategy": {"type": "object", "description": "Strategy to test"}
                },
                "required": ["strategy"]
            }
        }
    }
]


class TradingAgent:
    """
    Main agent that processes natural language trading ideas using an LLM.
    Combines AI understanding, strategy parsing, backtesting, and code generation.
    """

    def __init__(self):
        self.parser = StrategyParser()
        self.backtester = BacktestEngine()
        self.mt5_gen = MT5Generator()
        self.report_gen = ReportGenerator()
        self.llm = OpenRouterClient()
        self.system_prompt = SYSTEM_PROMPT
        print(f"[TradingAgent] Initialized. LLM connected: {self.llm.use_llm}")
        if self.llm.use_llm:
            print(f"[TradingAgent] Model: {self.llm.model}")

    async def process_message(
        self,
        message: str,
        images: List[str],
        session: str,
        sessions: Dict[str, dict]
    ) -> Dict[str, Any]:
        """
        Process a user message using the LLM agent.
        """
        result = {
            "response": "",
            "strategy": None,
            "backtest_results": None,
            "mt5_code": None
        }

        # Build conversation history from session
        messages = [{"role": "system", "content": self.system_prompt}]

        # Add previous messages from session history (last 10)
        if session in sessions:
            for msg in sessions[session].get("history", [])[-10:]:
                if msg.get("role") in ("user", "assistant"):
                    messages.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })

        # Add current user message
        user_content = message
        if images:
            user_content += f"\n[{len(images)} image(s) uploaded]"
        messages.append({"role": "user", "content": user_content})

        # Call LLM with tools
        llm_response = await self.llm.chat(messages, tools=TOOLS)

        if "error" in llm_response:
            error_msg = llm_response.get("message", "Unknown LLM error")
            print(f"[TradingAgent] LLM error: {error_msg}")

        # Process tool calls
        tool_calls = self.llm.extract_tool_calls(llm_response)
        strategy_ir = None
        backtest_results = None
        mt5_code = None
        mutation_results = None
        robustness_results = None

        for tc in tool_calls:
            func = tc.get("function", {})
            func_name = func.get("name", "")
            try:
                args = json.loads(func.get("arguments", "{}"))
            except json.JSONDecodeError:
                args = {}

            print(f"[TradingAgent] Tool call: {func_name}({list(args.keys())})")

            if func_name == "parse_strategy":
                text = args.get("text", message)
                strategy_ir = self.parser.parse(text, images if images else None)

            elif func_name == "run_backtest":
                strat = args.get("strategy")
                if strat:
                    backtest_results = self.backtester.run(
                        strategy=strat,
                        symbol=args.get("symbol", "EURUSD"),
                        timeframe=args.get("timeframe", "H1"),
                    )

            elif func_name == "generate_mt5":
                strat = args.get("strategy")
                if strat:
                    mt5_code = self.mt5_gen.generate(strat)

            elif func_name == "mutate_strategy":
                strat = args.get("strategy")
                if strat:
                    mutation_results = self.backtester.run(
                        strategy=strat,
                        symbol="EURUSD",
                        timeframe="H1",
                    )

            elif func_name == "run_robustness":
                strat = args.get("strategy")
                if strat:
                    robustness_results = self.backtester.run_robustness_tests(
                        strategy=strat,
                        n_monte_carlo=500,
                        n_walk_forward=3,
                    )

        # If no strategy was parsed by LLM, parse locally as fallback
        if strategy_ir is None:
            strategy_ir = self.parser.parse(message, images if images else None)

        # Build response
        response_parts = []

        # Get LLM's text response
        llm_content = self.llm.extract_content(llm_response)
        if llm_content and not llm_content.startswith("{"):
            response_parts.append(llm_content)
        else:
            # Fallback response if LLM didn't return text
            response_parts.append(self._acknowledge_idea(message, strategy_ir))
            response_parts.append(f"\n\n**Parsed Strategy:**\n{strategy_ir.summary()}")
            response_parts.append(self._explain_strategy(strategy_ir, message))

        if images:
            response_parts.append(f"\n\n**Images:** {len(images)} uploaded and analyzed.")

        if backtest_results:
            response_parts.append(self._format_backtest_summary(backtest_results))

        if mt5_code:
            response_parts.append(f"\n\n**MQL5 Code** ({len(mt5_code)} chars):")
            response_parts.append(f"```mql5\n{mt5_code[:2000]}...\n```")

        result["response"] = "\n".join(response_parts)
        result["strategy"] = strategy_ir.to_dict() if strategy_ir else None
        result["backtest_results"] = backtest_results
        result["mt5_code"] = mt5_code

        return result

    def _acknowledge_idea(self, message: str, strategy: StrategyIR) -> str:
        type_desc = {
            StrategyType.TREND_FOLLOWING: "trend following",
            StrategyType.MEAN_REVERSION: "mean reversion",
            StrategyType.BREAKOUT: "breakout",
            StrategyType.SCALPING: "scalping",
            StrategyType.SWING: "swing trading",
            StrategyType.ARBITRAGE: "arbitrage",
            StrategyType.OPTIONS: "options",
            StrategyType.CUSTOM: "custom",
        }
        strategy_type = type_desc.get(strategy.type, "custom")
        instruments = ", ".join(strategy.instruments) if strategy.instruments else "the market"
        timeframes = ", ".join(t.value for t in strategy.timeframes) if strategy.timeframes else "your preferred timeframe"
        return (
            f"I understand you want to build a **{strategy_type}** strategy on **{instruments}** "
            f"using the **{timeframes}** timeframe.\n\n"
            f"Let me break down what I've understood and the strategy I've constructed:"
        )

    def _explain_strategy(self, strategy: StrategyIR, original_message: str) -> str:
        lines = []
        if strategy.indicators:
            lines.append("\n**Indicators:**")
            for ind in strategy.indicators:
                params_str = ", ".join(f"{k}={v}" for k, v in ind.parameters.items())
                lines.append(f"  - {ind.type.value.upper()} ({params_str})")
        if strategy.entry_signals:
            lines.append("\n**Entry Rules:**")
            for sig in strategy.entry_signals:
                direction = "BUY" if sig.type == SignalType.BUY else "SELL"
                cond_str = self._format_conditions(sig.condition)
                lines.append(f"  - {direction}: {cond_str}")
        if strategy.exit_signals:
            lines.append("\n**Exit Rules:**")
            for sig in strategy.exit_signals:
                cond_str = self._format_conditions(sig.condition)
                lines.append(f"  - {sig.type.value}: {cond_str}")
        rm = strategy.risk_management
        lines.append("\n**Risk Management:**")
        if rm.stop_loss:
            lines.append(f"  - Stop Loss: {rm.stop_loss} ({rm.stop_loss_type})")
        if rm.take_profit:
            lines.append(f"  - Take Profit: {rm.take_profit} ({rm.take_profit_type})")
        if rm.trailing_stop:
            lines.append(f"  - Trailing Stop: {rm.trailing_stop}")
        if rm.risk_per_trade:
            lines.append(f"  - Risk per Trade: {rm.risk_per_trade}%")
        if not any([rm.stop_loss, rm.take_profit, rm.trailing_stop, rm.risk_per_trade]):
            lines.append("  - No specific risk management defined. Consider adding stop loss.")
        return "\n".join(lines)

    def _format_conditions(self, group: ConditionGroup) -> str:
        parts = []
        for cond in group.conditions:
            parts.append(f"{cond.left_operand} {cond.operator.value} {cond.right_operand}")
        for sub in group.sub_groups:
            parts.append(f"({self._format_conditions(sub)})")
        return f" {group.logic} ".join(parts) if parts else "No specific conditions"

    def _format_backtest_summary(self, results: dict) -> str:
        lines = ["\n**Backtest Results:**"]
        metrics = results.get("metrics", {})
        key_metrics = [
            "total_return", "sharpe_ratio", "sortino_ratio", "max_drawdown",
            "win_rate", "profit_factor", "total_trades", "calmar_ratio",
            "expectancy", "net_profit"
        ]
        for key in key_metrics:
            val = metrics.get(key)
            if val is not None:
                if isinstance(val, float):
                    lines.append(f"  - {key}: {val:.4f}")
                else:
                    lines.append(f"  - {key}: {val}")
        if results.get("trades"):
            lines.append(f"  - Number of trades: {len(results['trades'])}")
        return "\n".join(lines)
