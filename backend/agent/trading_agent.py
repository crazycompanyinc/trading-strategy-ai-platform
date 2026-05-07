"""
Trading Agent - NLP-powered agent with real tool execution.
Connected to OpenRouter LLM. Actually runs backtests, mutations,
MT5 generation, and robustness tests instead of just talking about them.
"""
from __future__ import annotations
import asyncio
import json
import os
import base64
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone
import urllib.request
import urllib.error

from strategy.parser import StrategyParser
from strategy.models import StrategyIR, StrategyType, SignalType, ConditionOperator, ConditionGroup
from backtester.engine import BacktestEngine
from mutator.genetic import GeneticMutator
from mt5.generator import MT5Generator
from reports.generator import ReportGenerator


SYSTEM_PROMPT = """You are an expert quantitative trading analyst and strategy developer. Your role is to:

1. **Understand** the user's trading idea deeply, no matter how vague or complex
2. **Research** concepts, indicators, or strategies mentioned
3. **Synthesize** a clear, actionable trading strategy with specific rules
4. **Execute** — you have REAL tools that actually run backtests, evolve strategies, and generate MT5 code
5. **Show results** — present backtest metrics, evolved strategies, and generated code

CRITICAL: When a user describes a trading idea, you MUST:
- First call parse_strategy to create a structured strategy
- Then call run_backtest to test it on real historical data
- Optionally call mutate_strategy to find better variants
- Optionally call generate_mt5 to create MQL5 code

DO NOT just describe what you WOULD do. Actually DO it by calling the tools.

Available instruments: EURUSD, GBPUSD, USDJPY, USDCHF, AUDUSD, USDCAD, NZDUSD, XAUUSD, BTCUSD
Available timeframes: M1, M5, M15, M30, H1, H4, D1, W1
Available indicators: sma, ema, wma, rsi, macd, bollinger_bands, atr, stochastic, cci, adx, obv, vwap

Respond in the same language the user writes in. Be thorough and educational.
"""


class OpenRouterClient:
    """Client for OpenRouter API."""

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
        max_tokens: int = 4096,
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
            "max_tokens": max_tokens,
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
            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(
                None, lambda: urllib.request.urlopen(req, timeout=120)
            )
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
                    "message": {"content": f"LLM connection error: {e}. Falling back to basic parsing."}
                }]
            }

    def extract_content(self, response: Dict) -> str:
        try:
            msg = response["choices"][0]["message"]
            content = msg.get("content")
            if content:
                return content
            tool_calls = msg.get("tool_calls", [])
            if tool_calls:
                return json.dumps({"tool_calls": tool_calls})
            return str(msg)
        except (KeyError, IndexError):
            return ""

    def extract_tool_calls(self, response: Dict) -> List[Dict]:
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
                    "text": {"type": "string", "description": "The user's natural language description"}
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_backtest",
            "description": "Run a backtest for a given strategy on historical data. ALWAYS call this after parsing a strategy.",
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
            "description": "Generate MQL5 Expert Advisor code from a strategy.",
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
            "description": "Evolve a strategy using genetic algorithms to find better variants.",
            "parameters": {
                "type": "object",
                "properties": {
                    "strategy": {"type": "object", "description": "Base strategy to mutate"},
                    "population_size": {"type": "integer", "description": "Population size, default 15"},
                    "generations": {"type": "integer", "description": "Number of generations, default 5"}
                },
                "required": ["strategy"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_robustness",
            "description": "Run robustness tests (Monte Carlo, walk-forward, sensitivity).",
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
    Actually executes tools: backtesting, mutation, MT5 generation.
    """

    def __init__(self):
        self.parser = StrategyParser()
        self.backtester = BacktestEngine()
        self.mutator = GeneticMutator()
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
        Process a user message. Executes tools in a loop until the LLM
        is done calling tools, then returns the final response.
        """
        result = {
            "response": "",
            "strategy": None,
            "backtest_results": None,
            "mt5_code": None,
            "mutation_results": None,
            "robustness_results": None,
        }

        # Build conversation history
        messages = [{"role": "system", "content": self.system_prompt}]

        if session in sessions:
            for msg in sessions[session].get("history", [])[-10:]:
                if msg.get("role") in ("user", "assistant"):
                    messages.append({"role": msg["role"], "content": msg["content"]})

        user_content = message
        if images:
            user_content += f"\n[{len(images)} image(s) uploaded]"
        messages.append({"role": "user", "content": user_content})

        # Tool execution loop — keep calling LLM until it stops requesting tools
        max_iterations = 5
        strategy_ir = None
        backtest_results = None
        mt5_code = None
        mutation_results = None
        robustness_results = None
        llm_content = ""

        for iteration in range(max_iterations):
            llm_response = await self.llm.chat(messages, tools=TOOLS)

            if "error" in llm_response:
                print(f"[TradingAgent] LLM error: {llm_response.get('message', 'Unknown')}")

            tool_calls = self.llm.extract_tool_calls(llm_response)
            llm_content = self.llm.extract_content(llm_response)

            if not tool_calls:
                # No more tool calls — LLM is done
                break

            # Add assistant message with tool calls to history
            messages.append({
                "role": "assistant",
                "content": llm_content,
                "tool_calls": tool_calls,
            })

            # Execute each tool call
            for tc in tool_calls:
                func = tc.get("function", {})
                func_name = func.get("name", "")
                try:
                    args = json.loads(func.get("arguments", "{}"))
                except json.JSONDecodeError:
                    args = {}

                print(f"[TradingAgent] Executing: {func_name}({list(args.keys())})")

                tool_result = {}

                if func_name == "parse_strategy":
                    text = args.get("text", message)
                    strategy_ir = self.parser.parse(text, images if images else None)
                    tool_result = {"strategy": strategy_ir.to_dict(), "summary": strategy_ir.summary()}

                elif func_name == "run_backtest":
                    strat = args.get("strategy")
                    if strat:
                        backtest_results = await asyncio.get_event_loop().run_in_executor(
                            None,
                            lambda: self.backtester.run(
                                strategy=strat,
                                symbol=args.get("symbol", "EURUSD"),
                                timeframe=args.get("timeframe", "H1"),
                            )
                        )
                        metrics = backtest_results.get("metrics", {})
                        tool_result = {
                            "total_return": metrics.get("total_return"),
                            "sharpe_ratio": metrics.get("sharpe_ratio"),
                            "max_drawdown": metrics.get("max_drawdown"),
                            "win_rate": metrics.get("win_rate"),
                            "profit_factor": metrics.get("profit_factor"),
                            "total_trades": metrics.get("total_trades"),
                        }

                elif func_name == "generate_mt5":
                    strat = args.get("strategy")
                    if strat:
                        mt5_code = await asyncio.get_event_loop().run_in_executor(
                            None, lambda: self.mt5_gen.generate(strat)
                        )
                        tool_result = {"code_length": len(mt5_code), "preview": mt5_code[:500]}

                elif func_name == "mutate_strategy":
                    strat = args.get("strategy")
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

                elif func_name == "run_robustness":
                    strat = args.get("strategy")
                    if strat:
                        robustness_results = await asyncio.get_event_loop().run_in_executor(
                            None,
                            lambda: self.backtester.run_robustness_tests(strategy=strat)
                        )
                        mc = robustness_results.get("monte_carlo", {})
                        tool_result = {
                            "prob_profit": mc.get("prob_profit"),
                            "worst_return": mc.get("worst_return"),
                            "var_95": mc.get("var_95"),
                        }

                # Add tool result to messages
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", f"call_{iteration}"),
                    "content": json.dumps(tool_result),
                })

        # Build final response
        response_parts = []

        if llm_content and not llm_content.startswith("{"):
            response_parts.append(llm_content)
        else:
            if strategy_ir:
                response_parts.append(self._acknowledge_idea(message, strategy_ir))
                response_parts.append(f"\n\n**Parsed Strategy:**\n{strategy_ir.summary()}")
                response_parts.append(self._explain_strategy(strategy_ir, message))

        if backtest_results:
            response_parts.append(self._format_backtest_summary(backtest_results))

        if mutation_results:
            response_parts.append(self._format_mutation_summary(mutation_results))

        if mt5_code:
            response_parts.append(f"\n\n**MQL5 Code** ({len(mt5_code)} chars):")
            response_parts.append(f"```mql5\n{mt5_code[:2000]}...\n```")

        if robustness_results:
            response_parts.append(self._format_robustness_summary(robustness_results))

        if not response_parts:
            response_parts.append(llm_content or "I've processed your request. No specific actions were needed.")

        result["response"] = "\n".join(response_parts)
        result["strategy"] = strategy_ir.to_dict() if strategy_ir else None
        result["backtest_results"] = backtest_results
        result["mt5_code"] = mt5_code
        result["mutation_results"] = mutation_results
        result["robustness_results"] = robustness_results

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

    def _format_mutation_summary(self, results: dict) -> str:
        lines = ["\n**Genetic Evolution:**"]
        lines.append(f"  - Strategies evaluated: {results.get('total_evaluated', 0)}")
        lines.append(f"  - Generations run: {results.get('generations_run', 0)}")
        best = results.get("best_strategies", [])
        if best:
            best_m = best[0].get("metrics", {})
            lines.append(f"  - Best Sharpe: {best_m.get('sharpe_ratio', 0):.2f}")
            lines.append(f"  - Best Return: {best_m.get('total_return', 0):.1f}%")
            lines.append(f"  - Best Win Rate: {best_m.get('win_rate', 0):.1f}%")
        return "\n".join(lines)

    def _format_robustness_summary(self, results: dict) -> str:
        lines = ["\n**Robustness Tests:**"]
        mc = results.get("monte_carlo", {})
        if mc:
            lines.append(f"  - Monte Carlo simulations: {mc.get('n_simulations', 0)}")
            lines.append(f"  - Probability of profit: {mc.get('prob_profit', 0):.1f}%")
            lines.append(f"  - Worst return: {mc.get('worst_return', 0):.1f}%")
            lines.append(f"  - VaR 95%: {mc.get('var_95', 0):.1f}%")
        wf = results.get("walk_forward", {})
        if wf:
            lines.append(f"  - Walk-forward windows: {wf.get('n_windows', 0)}")
            lines.append(f"  - Consistency score: {wf.get('consistency_score', 0):.2f}")
        return "\n".join(lines)
