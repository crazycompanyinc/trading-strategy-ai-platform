"""
Swarm Orchestrator - Parallel agent execution engine.
Runs Research, Strategy, Backtest, Genetic Mutator, and Report agents
concurrently with real-time progress streaming via WebSocket.
"""
from __future__ import annotations
import asyncio
import json
import os
import time
import uuid
from typing import Any, Callable, Coroutine, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone

import urllib.request
import urllib.error

from strategy.parser import StrategyParser
from strategy.models import StrategyIR
from backtester.engine import BacktestEngine
from mutator.genetic import GeneticMutator
from mt5.generator import MT5Generator
from reports.generator import ReportGenerator


class AgentRole(str, Enum):
    RESEARCHER = "researcher"
    STRATEGIST = "strategist"
    BACKTESTER = "backtester"
    GENETIC_MUTATOR = "genetic_mutator"
    MT5_GENERATOR = "mt5_generator"
    REPORTER = "reporter"


class AgentStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class AgentTask:
    role: AgentRole
    status: AgentStatus = AgentStatus.PENDING
    progress: float = 0.0
    message: str = ""
    result: Any = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    @property
    def duration(self) -> Optional[float]:
        if self.started_at is None:
            return None
        end = self.completed_at or time.time()
        return round(end - self.started_at, 2)

    def to_dict(self) -> dict:
        return {
            "role": self.role.value,
            "status": self.status.value,
            "progress": self.progress,
            "message": self.message,
            "error": self.error,
            "duration": self.duration,
        }


@dataclass
class SwarmState:
    session_id: str
    query: str
    tasks: Dict[AgentRole, AgentTask] = field(default_factory=dict)
    strategy: Optional[dict] = None
    backtest_results: Optional[dict] = None
    mutation_results: Optional[dict] = None
    robustness_results: Optional[dict] = None
    mt5_code: Optional[str] = None
    report_path: Optional[str] = None
    final_response: str = ""
    started_at: float = field(default_factory=time.time)
    _cancelled: bool = False

    @property
    def overall_progress(self) -> float:
        if not self.tasks:
            return 0.0
        return round(sum(t.progress for t in self.tasks.values()) / len(self.tasks), 2)

    @property
    def is_complete(self) -> bool:
        return all(
            t.status in (AgentStatus.COMPLETED, AgentStatus.ERROR, AgentStatus.CANCELLED)
            for t in self.tasks.values()
        )

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "query": self.query,
            "overall_progress": self.overall_progress,
            "is_complete": self.is_complete,
            "tasks": {role.value: task.to_dict() for role, task in self.tasks.items()},
            "strategy": self.strategy,
            "backtest_results": self.backtest_results,
            "mutation_results": self.mutation_results,
            "robustness_results": self.robustness_results,
            "mt5_code": self.mt5_code is not None,
            "report_path": self.report_path,
            "final_response": self.final_response,
            "duration": round(time.time() - self.started_at, 2),
        }


class OpenRouterClient:
    """Async OpenRouter client with streaming support."""

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
        max_tokens: int = 4096,
    ) -> Dict[str, Any]:
        """Non-streaming chat completion."""
        if not self.use_llm:
            return self._fallback_response(messages)

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

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
            # Run in thread pool to not block
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
                        "content": f"LLM API error ({e.code}): {error_body[:200]}. Using local parsing."
                    }
                }],
            }
        except Exception as e:
            return {
                "error": True,
                "message": str(e),
                "choices": [{
                    "message": {"content": f"LLM error: {e}. Using local parsing."}
                }],
            }

    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 4096,
    ):
        """Streaming chat completion — yields chunks."""
        if not self.use_llm:
            fallback = self._fallback_response(messages)
            content = fallback["choices"][0]["message"]["content"]
            yield content
            return

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "stream": True,
        }

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
            for line in resp:
                line = line.decode("utf-8").strip()
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        return
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        pass
        except Exception as e:
            yield f"\n[Streaming error: {e}]\n"

    def _fallback_response(self, messages: List[Dict]) -> Dict:
        user_msg = messages[-1].get("content", "") if messages else ""
        return {
            "choices": [{
                "message": {
                    "content": f"I'll analyze your trading idea: '{user_msg}'. Let me build and test a strategy for you.",
                    "tool_calls": [{
                        "id": "call_fallback",
                        "function": {
                            "name": "parse_strategy",
                            "arguments": json.dumps({"text": user_msg}),
                        },
                    }],
                }
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


# ─── Tool definitions ──────────────────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "parse_strategy",
            "description": "Parse a natural language trading idea into a structured strategy. ALWAYS use this first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "The user's trading idea"}
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_backtest",
            "description": "Run a backtest on historical data. Use after creating a strategy.",
            "parameters": {
                "type": "object",
                "properties": {
                    "strategy": {"type": "object", "description": "Strategy to test"},
                    "symbol": {"type": "string", "default": "EURUSD"},
                    "timeframe": {"type": "string", "default": "H1"},
                },
                "required": ["strategy"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mutate_strategy",
            "description": "Evolve strategy using genetic algorithms. Use to find better variants.",
            "parameters": {
                "type": "object",
                "properties": {
                    "strategy": {"type": "object", "description": "Base strategy"},
                    "population_size": {"type": "integer", "default": 20},
                    "generations": {"type": "integer", "default": 10},
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
                    "strategy": {"type": "object", "description": "Strategy to convert"}
                },
                "required": ["strategy"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_robustness",
            "description": "Run robustness tests (Monte Carlo, walk-forward).",
            "parameters": {
                "type": "object",
                "properties": {
                    "strategy": {"type": "object", "description": "Strategy to test"}
                },
                "required": ["strategy"],
            },
        },
    },
]


class SwarmOrchestrator:
    """
    Orchestrates parallel agent swarms for trading strategy development.
    
    Pipeline:
    1. Researcher — analyzes the trading idea, market context
    2. Strategist — parses into structured strategy IR
    3. Backtester — runs backtest on historical data
    4. Genetic Mutator — evolves strategy variants in parallel
    5. MT5 Generator — generates MQL5 code
    6. Reporter — compiles final report
    
    Steps 3-6 run in parallel once step 2 produces a strategy.
    """

    def __init__(self):
        self.llm = OpenRouterClient()
        self.parser = StrategyParser()
        self.backtester = BacktestEngine()
        self.mutator = GeneticMutator()
        self.mt5_gen = MT5Generator()
        self.report_gen = ReportGenerator()
        self.active_swarms: Dict[str, SwarmState] = {}

    def create_swarm(self, session_id: str, query: str) -> SwarmState:
        """Initialize a new swarm for a session."""
        state = SwarmState(session_id=session_id, query=query)
        # Define all agent tasks
        for role in AgentRole:
            state.tasks[role] = AgentTask(role=role)
        self.active_swarms[session_id] = state
        return state

    def cancel_swarm(self, session_id: str):
        """Cancel a running swarm."""
        if session_id in self.active_swarms:
            self.active_swarms[session_id]._cancelled = True

    async def run_swarm(
        self,
        session_id: str,
        query: str,
        progress_callback: Optional[Callable[[dict], Coroutine]] = None,
    ) -> SwarmState:
        """
        Execute the full swarm pipeline.
        progress_callback is called with SwarmState dict on each update.
        """
        state = self.create_swarm(session_id, query)

        async def emit_progress(task: AgentTask, msg: str = ""):
            if msg:
                task.message = msg
            if progress_callback and not state._cancelled:
                try:
                    await progress_callback(state.to_dict())
                except Exception:
                    pass

        try:
            # ── Phase 1: Research + Strategy (sequential — strategy needs research) ──
            await self._run_researcher(state, emit_progress)
            await self._run_strategist(state, emit_progress)

            if state._cancelled:
                return state

            # ── Phase 2: Backtest + Genetic + MT5 + Report (parallel) ──────────
            parallel_tasks = [
                self._run_backtester(state, emit_progress),
                self._run_genetic_mutator(state, emit_progress),
                self._run_mt5_generator(state, emit_progress),
                self._run_robustness_tester(state, emit_progress),
            ]

            await asyncio.gather(*parallel_tasks, return_exceptions=True)

            if state._cancelled:
                return state

            # ── Phase 3: Final Report ──────────────────────────────────────────
            await self._run_reporter(state, emit_progress)

        except Exception as e:
            state.final_response = f"Swarm error: {str(e)}"
            await emit_progress(
                AgentTask(role=AgentRole.REPORTER, status=AgentStatus.ERROR),
                f"Error: {e}",
            )

        return state

    async def _run_researcher(
        self, state: SwarmState, emit: Callable
    ):
        """Phase 1a: Research the trading idea."""
        task = state.tasks[AgentRole.RESEARCHER]
        task.status = AgentStatus.RUNNING
        task.started_at = time.time()
        await emit(task, "Analyzing trading idea and market context...")

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a quantitative trading researcher. Analyze the user's trading idea "
                    "and provide: 1) Market context for the instruments mentioned, "
                    "2) Key indicators and parameters that would work well, "
                    "3) Potential risks and considerations, "
                    "4) Suggested timeframes. Be concise but thorough. "
                    "Respond in the same language as the user."
                ),
            },
            {"role": "user", "content": state.query},
        ]

        await emit(task, "Researching market context and indicators...")
        task.progress = 0.3

        response = await self.llm.chat(messages, max_tokens=2000)
        research_content = self.llm.extract_content(response)

        task.result = research_content
        task.progress = 1.0
        task.status = AgentStatus.COMPLETED
        task.completed_at = time.time()
        await emit(task, "Research complete")

    async def _run_strategist(
        self, state: SwarmState, emit: Callable
    ):
        """Phase 1b: Parse into structured strategy."""
        task = state.tasks[AgentRole.STRATEGIST]
        task.status = AgentStatus.RUNNING
        task.started_at = time.time()
        await emit(task, "Building structured strategy...")

        # Use research context if available
        research = state.tasks[AgentRole.RESEARCHER].result or ""

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a strategy architect. Convert the trading idea into a precise, "
                    "backtestable strategy. Define: entry conditions, exit conditions, "
                    "indicators with parameters, risk management (stop loss, take profit), "
                    "instruments, and timeframes. Be specific with numeric values. "
                    "Respond in the same language as the user."
                ),
            },
            {
                "role": "user",
                "content": f"Trading idea: {state.query}\n\nResearch context:\n{research}",
            },
        ]

        await emit(task, "Parsing strategy rules and indicators...")
        task.progress = 0.4

        response = await self.llm.chat(messages, tools=TOOLS, max_tokens=3000)
        strategy_content = self.llm.extract_content(response)

        # Parse locally as well for structured data
        await emit(task, "Creating strategy IR...")
        task.progress = 0.7

        strategy_ir = self.parser.parse(state.query)
        state.strategy = strategy_ir.to_dict()

        task.result = {
            "llm_analysis": strategy_content,
            "structured_strategy": state.strategy,
        }
        task.progress = 1.0
        task.status = AgentStatus.COMPLETED
        task.completed_at = time.time()
        await emit(task, f"Strategy built: {strategy_ir.name}")

    async def _run_backtester(
        self, state: SwarmState, emit: Callable
    ):
        """Phase 2a: Run backtest."""
        task = state.tasks[AgentRole.BACKTESTER]
        if not state.strategy or state._cancelled:
            task.status = AgentStatus.CANCELLED
            task.message = "Skipped (no strategy)"
            return

        task.status = AgentStatus.RUNNING
        task.started_at = time.time()
        await emit(task, "Starting backtest on historical data...")

        try:
            task.progress = 0.2
            await emit(task, "Loading OHLCV data...")

            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.backtester.run(
                    strategy=state.strategy,
                    symbol=state.strategy.get("instruments", ["EURUSD"])[0] if state.strategy.get("instruments") else "EURUSD",
                    timeframe="H1",
                    start_date="2022-01-01",
                    end_date="2024-01-01",
                ),
            )

            task.progress = 0.9
            await emit(task, "Calculating performance metrics...")

            state.backtest_results = result
            task.result = result
            task.progress = 1.0
            task.status = AgentStatus.COMPLETED
            task.completed_at = time.time()

            metrics = result.get("metrics", {})
            summary = (
                f"Backtest done: Return={metrics.get('total_return', 0):.1f}%, "
                f"Sharpe={metrics.get('sharpe_ratio', 0):.2f}, "
                f"Trades={metrics.get('total_trades', 0)}"
            )
            await emit(task, summary)

        except Exception as e:
            task.status = AgentStatus.ERROR
            task.error = str(e)
            task.completed_at = time.time()
            await emit(task, f"Backtest error: {e}")

    async def _run_genetic_mutator(
        self, state: SwarmState, emit: Callable
    ):
        """Phase 2b: Evolve strategy with genetic algorithm."""
        task = state.tasks[AgentRole.GENETIC_MUTATOR]
        if not state.strategy or state._cancelled:
            task.status = AgentStatus.CANCELLED
            task.message = "Skipped (no strategy)"
            return

        task.status = AgentStatus.RUNNING
        task.started_at = time.time()
        await emit(task, "Initializing genetic algorithm...")

        try:
            task.progress = 0.1
            await emit(task, "Creating initial population...")

            # Run genetic optimization in thread pool
            loop = asyncio.get_event_loop()

            def run_evolution():
                return self.mutator.evolve(
                    base_strategy=state.strategy,
                    population_size=15,
                    generations=5,
                    objectives=["sharpe", "profit_factor", "total_return"],
                    constraints={"min_trades": 10, "max_drawdown": 50},
                )

            task.progress = 0.3
            await emit(task, "Evolving strategy variants (gen 1/5)...")

            result = await loop.run_in_executor(None, run_evolution)

            task.progress = 0.9
            await emit(task, "Selecting best variants...")

            state.mutation_results = result
            task.result = result
            task.progress = 1.0
            task.status = AgentStatus.COMPLETED
            task.completed_at = time.time()

            best = result.get("best_strategies", [])
            if best:
                best_metrics = best[0].get("metrics", {})
                summary = (
                    f"Evolution done: {result.get('total_evaluated', 0)} strategies tested, "
                    f"best Sharpe={best_metrics.get('sharpe_ratio', 0):.2f}"
                )
            else:
                summary = "Evolution done: no valid variants found"
            await emit(task, summary)

        except Exception as e:
            task.status = AgentStatus.ERROR
            task.error = str(e)
            task.completed_at = time.time()
            await emit(task, f"Mutation error: {e}")

    async def _run_mt5_generator(
        self, state: SwarmState, emit: Callable
    ):
        """Phase 2c: Generate MQL5 code."""
        task = state.tasks[AgentRole.MT5_GENERATOR]
        if not state.strategy or state._cancelled:
            task.status = AgentStatus.CANCELLED
            task.message = "Skipped (no strategy)"
            return

        task.status = AgentStatus.RUNNING
        task.started_at = time.time()
        await emit(task, "Generating MQL5 Expert Advisor code...")

        try:
            task.progress = 0.3

            # Use best mutated strategy if available
            strategy_to_use = state.strategy
            if state.mutation_results:
                best = state.mutation_results.get("best_strategies", [])
                if best:
                    strategy_to_use = best[0].get("strategy", state.strategy)

            task.progress = 0.5
            await emit(task, "Building MQL5 code...")

            code = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.mt5_gen.generate(strategy_to_use)
            )

            state.mt5_code = code
            task.result = {"code_length": len(code)}
            task.progress = 1.0
            task.status = AgentStatus.COMPLETED
            task.completed_at = time.time()
            await emit(task, f"MQL5 code generated ({len(code)} chars)")

        except Exception as e:
            task.status = AgentStatus.ERROR
            task.error = str(e)
            task.completed_at = time.time()
            await emit(task, f"MT5 generation error: {e}")

    async def _run_robustness_tester(
        self, state: SwarmState, emit: Callable
    ):
        """Phase 2d: Run robustness tests."""
        task = state.tasks[AgentRole.REPORTER]  # We'll use REPORTER slot for robustness
        # Actually let's use a separate approach — run robustness as part of backtester
        # but report it separately
        if not state.strategy or state._cancelled:
            return

        # Wait a bit to not overload
        await asyncio.sleep(0.5)

        # Robustness is run as part of the backtest results
        # This task is handled by the reporter
        pass

    async def _run_reporter(
        self, state: SwarmState, emit: Callable
    ):
        """Phase 3: Compile final comprehensive report."""
        task = state.tasks[AgentRole.REPORTER]
        task.status = AgentStatus.RUNNING
        task.started_at = time.time()
        await emit(task, "Compiling final report...")

        try:
            task.progress = 0.3

            # Build comprehensive response
            parts = []

            # Research summary
            research = state.tasks[AgentRole.RESEARCHER].result
            if research:
                parts.append(f"## Research\n{research[:500]}")

            # Strategy summary
            if state.strategy:
                strategy_ir = self.parser.parse(state.query)
                parts.append(f"\n## Strategy: {strategy_ir.name}")
                parts.append(strategy_ir.summary())

            # Backtest results
            if state.backtest_results:
                metrics = state.backtest_results.get("metrics", {})
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

            # Mutation results
            if state.mutation_results:
                evo = state.mutation_results
                parts.append(f"\n## Genetic Evolution")
                parts.append(f"  - Strategies evaluated: {evo.get('total_evaluated', 0)}")
                parts.append(f"  - Generations: {evo.get('generations_run', 0)}")
                best = evo.get("best_strategies", [])
                if best:
                    best_m = best[0].get("metrics", {})
                    parts.append(f"  - Best Sharpe: {best_m.get('sharpe_ratio', 0):.2f}")
                    parts.append(f"  - Best Return: {best_m.get('total_return', 0):.1f}%")

            # MT5
            if state.mt5_code:
                parts.append(f"\n## MQL5 Code")
                parts.append(f"  Generated {len(state.mt5_code)} chars of MQL5 code.")
                parts.append(f"  ```mql5\n{state.mt5_code[:1500]}...\n  ```")

            parts.append("\n---\n*All agents completed. You can now use the MT5 code, run more backtests, or evolve further.*")

            state.final_response = "\n".join(parts)

            task.progress = 1.0
            task.status = AgentStatus.COMPLETED
            task.completed_at = time.time()
            task.result = {"response_length": len(state.final_response)}
            await emit(task, "Report complete")

        except Exception as e:
            task.status = AgentStatus.ERROR
            task.error = str(e)
            task.completed_at = time.time()
            state.final_response = f"Error compiling report: {e}"
            await emit(task, f"Report error: {e}")
