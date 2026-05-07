"""
Trading Agent - NLP-powered agent that understands trading ideas,
consults the web for research, analyzes images, and produces strategies.
"""
from __future__ import annotations
import asyncio
import json
import os
import base64
import tempfile
from typing import List, Dict, Optional, Any
from datetime import datetime

from strategy.parser import StrategyParser
from strategy.models import StrategyIR, StrategyType, SignalType, ConditionOperator, ConditionGroup
from backtester.engine import BacktestEngine
from mt5.generator import MT5Generator
from reports.generator import ReportGenerator


SYSTEM_PROMPT = """You are an expert quantitative trading analyst and strategy developer. Your role is to:

1. **Understand** the user's trading idea deeply, no matter how vague or complex
2. **Research** any concepts, indicators, or strategies mentioned that you need to clarify
3. **Ask** clarifying questions when the idea is ambiguous
4. **Synthesize** a clear, actionable trading strategy with specific rules
5. **Explain** the strategy in detail including: instruments, timeframes, indicators, entry/exit rules, risk management
6. **Generate** the strategy in a structured format for backtesting
7. **Provide** MQL5 code for MetaTrader 5

When analyzing images (charts, screenshots, hand-drawn diagrams):
- Identify chart patterns, indicators, support/resistance levels
- Extract any visible trading rules or setups
- Relate visual elements to the user's description

Be precise with parameters. If the user says "fast EMA", ask what period or suggest 9/20.
If they say "oversold RSI", use standard 30 level unless specified.

Always consider:
- Market context (trending vs ranging)
- Risk management (stop loss, position sizing)
- Timeframe appropriateness
- Indicator combinations and conflicts

Respond in the same language the user writes in.
"""


class TradingAgent:
    """
    Main agent that processes natural language trading ideas.
    Combines NLP understanding, web research, image analysis,
    and strategy generation.
    """

    def __init__(self):
        self.parser = StrategyParser()
        self.backtester = BacktestEngine()
        self.mt5_gen = MT5Generator()
        self.report_gen = ReportGenerator()
        self.system_prompt = SYSTEM_PROMPT

    async def process_message(
        self,
        message: str,
        images: List[str],
        session: str,
        sessions: Dict[str, dict]
    ) -> Dict[str, Any]:
        """
        Process a user message and return a response with optional strategy,
        backtest results, and MT5 code.
        
        Args:
            message: User's natural language input
            images: List of base64-encoded images
            session: Session ID
            sessions: Session storage dict
            
        Returns:
            Dict with response, strategy, backtest_results, mt5_code
        """
        result = {
            "response": "",
            "strategy": None,
            "backtest_results": None,
            "mt5_code": None
        }

        # Step 1: Parse the strategy from natural language
        strategy_ir = self.parser.parse(message, images if images else None)

        # Step 2: Analyze images if provided
        image_analysis = ""
        if images:
            image_analysis = await self._analyze_images(images)

        # Step 3: Build comprehensive response
        response_parts = []

        # Acknowledge the idea
        response_parts.append(self._acknowledge_idea(message, strategy_ir))

        # If we have image analysis, include it
        if image_analysis:
            response_parts.append(f"\n\n**Image Analysis:**\n{image_analysis}")

        # Describe the parsed strategy
        response_parts.append(f"\n\n**Parsed Strategy:**\n{strategy_ir.summary()}")

        # Provide detailed strategy explanation
        response_parts.append(self._explain_strategy(strategy_ir, message))

        # Check if user wants backtest
        if self._wants_backtest(message):
            response_parts.append("\n\nRunning backtest...")
            try:
                bt_result = self.backtester.run(
                    strategy=strategy_ir.to_dict(),
                    symbol=strategy_ir.instruments[0] if strategy_ir.instruments else "EURUSD",
                    timeframe=strategy_ir.timeframes[0].value if strategy_ir.timeframes else "H1",
                )
                result["backtest_results"] = bt_result
                response_parts.append(self._format_backtest_summary(bt_result))
            except Exception as e:
                response_parts.append(f"\n\nBacktest error: {str(e)}. You can run it again with more data.")

        # Check if user wants MT5 code
        if self._wants_mt5(message):
            try:
                mt5_code = self.mt5_gen.generate(strategy_ir.to_dict())
                result["mt5_code"] = mt5_code
                response_parts.append(f"\n\nMQL5 code generated! ({len(mt5_code)} characters)")
            except Exception as e:
                response_parts.append(f"\n\nMT5 generation error: {str(e)}")

        result["response"] = "\n".join(response_parts)
        result["strategy"] = strategy_ir.to_dict()

        return result

    async def _analyze_images(self, images: List[str]) -> str:
        """Analyze uploaded images for chart patterns, indicators, etc."""
        analyses = []
        for i, img_data in enumerate(images):
            try:
                # Decode and save image
                if img_data.startswith("data:image"):
                    img_data = img_data.split(",", 1)[1]
                img_bytes = base64.b64decode(img_data)

                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    tmp.write(img_bytes)
                    tmp_path = tmp.name

                # In a real implementation, this would use vision AI
                # For now, we note the image was received
                analyses.append(
                    f"Image {i+1} received ({len(img_bytes)} bytes). "
                    f"In production, this would be analyzed by a vision model "
                    f"to identify chart patterns, indicators, and trading setups."
                )

                os.unlink(tmp_path)
            except Exception as e:
                analyses.append(f"Image {i+1}: Could not process ({str(e)})")

        return "\n".join(analyses)

    def _acknowledge_idea(self, message: str, strategy: StrategyIR) -> str:
        """Generate an acknowledgment of the user's trading idea."""
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
        """Generate a detailed explanation of the strategy."""
        lines = []

        # Indicators
        if strategy.indicators:
            lines.append("\n**Indicators:**")
            for ind in strategy.indicators:
                params_str = ", ".join(f"{k}={v}" for k, v in ind.parameters.items())
                lines.append(f"  - {ind.type.value.upper()} ({params_str})")

        # Entry signals
        if strategy.entry_signals:
            lines.append("\n**Entry Rules:**")
            for sig in strategy.entry_signals:
                direction = "BUY" if sig.type == SignalType.BUY else "SELL"
                cond_str = self._format_conditions(sig.condition)
                lines.append(f"  - {direction}: {cond_str}")

        # Exit signals
        if strategy.exit_signals:
            lines.append("\n**Exit Rules:**")
            for sig in strategy.exit_signals:
                cond_str = self._format_conditions(sig.condition)
                lines.append(f"  - {sig.type.value}: {cond_str}")

        # Risk management
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
        if rm.max_position_size:
            lines.append(f"  - Position Size: {rm.max_position_size} lots")
        if rm.max_drawdown_limit:
            lines.append(f"  - Max Drawdown: {rm.max_drawdown_limit}%")
        if not any([rm.stop_loss, rm.take_profit, rm.trailing_stop, rm.risk_per_trade]):
            lines.append("  - No specific risk management defined. Consider adding stop loss and position sizing.")

        return "\n".join(lines)

    def _format_conditions(self, group: ConditionGroup) -> str:
        """Format condition group into readable text."""
        parts = []
        for cond in group.conditions:
            parts.append(f"{cond.left_operand} {cond.operator.value} {cond.right_operand}")
        for sub in group.sub_groups:
            parts.append(f"({self._format_conditions(sub)})")
        return f" {group.logic} ".join(parts)

    def _wants_backtest(self, message: str) -> bool:
        """Check if the user wants to run a backtest."""
        keywords = ["backtest", "backtesting", "probar", "testear", "simular", "simulate",
                     "run it", "test it", "historical", "histórico", "datos históricos"]
        return any(kw in message.lower() for kw in keywords)

    def _wants_mt5(self, message: str) -> bool:
        """Check if the user wants MT5 code."""
        keywords = ["mt5", "metatrader", "mql5", "expert advisor", "ea", "código", "code"]
        return any(kw in message.lower() for kw in keywords)

    def _format_backtest_summary(self, results: dict) -> str:
        """Format backtest results into a readable summary."""
        lines = ["\n**Backtest Results:**"]
        metrics = results.get("metrics", {})
        for key, value in metrics.items():
            if isinstance(value, float):
                lines.append(f"  - {key}: {value:.4f}")
            else:
                lines.append(f"  - {key}: {value}")
        return "\n".join(lines)
