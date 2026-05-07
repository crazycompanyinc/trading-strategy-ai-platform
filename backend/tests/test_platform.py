"""
Trading Strategy AI Platform - Test Suite
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategy.parser import StrategyParser
from strategy.models import StrategyIR, StrategyType, IndicatorType, Timeframe
from backtester.engine import BacktestEngine
from mutator.genetic import GeneticMutator
from mt5.generator import MT5Generator
from reports.generator import ReportGenerator


class TestStrategyParser:
    def setup_method(self):
        self.parser = StrategyParser()

    def test_parse_trend_following(self):
        text = "Create a trend following strategy on EURUSD H1 using EMA crossover with RSI filter"
        ir = self.parser.parse(text)
        assert ir.type == StrategyType.TREND_FOLLOWING
        assert "EURUSD" in ir.instruments
        assert Timeframe.H1 in ir.timeframes
        assert len(ir.indicators) >= 1

    def test_parse_mean_reversion(self):
        text = "Mean reversion strategy on GBPUSD using Bollinger Bands and RSI on H4"
        ir = self.parser.parse(text)
        assert ir.type == StrategyType.MEAN_REVERSION
        assert "GBPUSD" in ir.instruments

    def test_parse_with_risk_management(self):
        text = "Buy EURUSD when RSI crosses below 30 with stop loss of 50 pips and take profit of 100 pips"
        ir = self.parser.parse(text)
        assert ir.risk_management.stop_loss == 50
        assert ir.risk_management.take_profit == 100

    def test_parse_breakout(self):
        text = "Breakout strategy on XAUUSD daily with ATR-based stop loss"
        ir = self.parser.parse(text)
        assert ir.type == StrategyType.BREAKOUT
        assert "XAUUSD" in ir.instruments

    def test_parse_scalping(self):
        text = "Scalping strategy on EURUSD M15 using MACD and stochastic"
        ir = self.parser.parse(text)
        assert ir.type == StrategyType.SCALPING

    def test_extract_multiple_indicators(self):
        text = "Use SMA 20, EMA 50, RSI 14, and MACD on EURUSD"
        ir = self.parser.parse(text)
        indicator_types = [ind.type for ind in ir.indicators]
        assert IndicatorType.SMA in indicator_types
        assert IndicatorType.EMA in indicator_types
        assert IndicatorType.RSI in indicator_types

    def test_parse_spanish(self):
        text = "Estrategia de seguimiento de tendencia en EURUSD con cruce de medias móviles"
        ir = self.parser.parse(text)
        assert ir.type == StrategyType.TREND_FOLLOWING

    def test_to_json_roundtrip(self):
        text = "Trend following on EURUSD H1 with EMA 20 and RSI 14"
        ir = self.parser.parse(text)
        json_str = self.parser.to_json(ir)
        ir2 = self.parser.from_json(json_str)
        assert ir2.type == ir.type
        assert ir2.instruments == ir.instruments


class TestBacktestEngine:
    def setup_method(self):
        self.engine = BacktestEngine()

    def test_basic_backtest(self):
        strategy = {
            "name": "Test Strategy",
            "indicators": [{"type": "sma", "parameters": {"period": 20}}],
            "entry_signals": [{"type": "buy", "condition": {"logic": "AND", "conditions": []}}],
            "exit_signals": [],
            "risk_management": {"stop_loss": 50, "take_profit": 100},
        }
        result = self.engine.run(strategy=strategy)
        assert "metrics" in result
        assert "trades" in result
        assert "equity_curve" in result
        assert result["metrics"]["total_trades"] >= 0

    def test_metrics_calculated(self):
        strategy = {
            "name": "Test",
            "indicators": [{"type": "ema", "parameters": {"period": 10}}],
            "entry_signals": [{"type": "buy", "condition": {"logic": "AND", "conditions": []}}],
            "exit_signals": [],
            "risk_management": {},
        }
        result = self.engine.run(strategy=strategy)
        metrics = result["metrics"]
        assert "sharpe_ratio" in metrics
        assert "sortino_ratio" in metrics
        assert "max_drawdown" in metrics
        assert "win_rate" in metrics
        assert "profit_factor" in metrics
        assert "calmar_ratio" in metrics
        assert "omega_ratio" in metrics
        assert "expectancy" in metrics

    def test_monte_carlo(self):
        # Use a strategy that generates enough trades via synthetic data
        strategy = {
            "name": "MC Test",
            "indicators": [{"type": "sma", "parameters": {"period": 5}}],
            "entry_signals": [{"type": "buy", "condition": {"logic": "AND", "conditions": [
                {"left_operand": "close", "operator": "crosses_above", "right_operand": "sma(5)"}
            ]}}],
            "exit_signals": [],
            "risk_management": {"stop_loss": 0.0050, "take_profit": 0.0100},
        }
        bt_result = self.engine.run(strategy=strategy)
        if bt_result["metrics"]["total_trades"] > 0:
            mc = self.engine._monte_carlo_test(strategy, n_simulations=100, confidence=0.95)
            assert "n_simulations" in mc
            assert "mean_return" in mc
            assert "prob_profit" in mc
        else:
            # If no trades, MC returns error - that's valid behavior
            mc = self.engine._monte_carlo_test(strategy, n_simulations=100, confidence=0.95)
            assert "error" in mc

    def test_walk_forward(self):
        strategy = {
            "name": "WF Test",
            "indicators": [{"type": "sma", "parameters": {"period": 20}}],
            "entry_signals": [{"type": "buy", "condition": {"logic": "AND", "conditions": []}}],
            "exit_signals": [],
            "risk_management": {},
        }
        wf = self.engine._walk_forward_test(strategy, n_windows=3)
        assert "n_windows" in wf
        assert "windows" in wf
        assert len(wf["windows"]) == 3

    def test_sensitivity(self):
        strategy = {
            "name": "Sens Test",
            "indicators": [{"type": "sma", "parameters": {"period": 20}}],
            "entry_signals": [{"type": "buy", "condition": {"logic": "AND", "conditions": []}}],
            "exit_signals": [],
            "risk_management": {},
        }
        sens = self.engine._sensitivity_analysis(strategy)
        assert "perturbations" in sens
        assert len(sens["perturbations"]) > 0


class TestGeneticMutator:
    def setup_method(self):
        self.mutator = GeneticMutator()

    def test_mutation_creates_variants(self):
        base = {
            "name": "Base",
            "indicators": [{"type": "sma", "parameters": {"period": 20}}],
            "entry_signals": [{"type": "buy", "condition": {"logic": "AND", "conditions": []}}],
            "exit_signals": [],
            "risk_management": {"stop_loss": 50, "take_profit": 100},
        }
        mutant = self.mutator._random_mutate(base, mutation_rate=0.5)
        assert mutant is not None

    def test_evolve_runs(self):
        base = {
            "name": "Evolve Test",
            "indicators": [{"type": "sma", "parameters": {"period": 20}}],
            "entry_signals": [{"type": "buy", "condition": {"logic": "AND", "conditions": []}}],
            "exit_signals": [],
            "risk_management": {"stop_loss": 50, "take_profit": 100},
        }
        result = self.mutator.evolve(
            base_strategy=base,
            population_size=6,
            generations=2,
            objectives=["sharpe"],
            constraints={"min_trades": 5},
        )
        assert "best_strategies" in result
        assert "evolution_history" in result
        assert len(result["evolution_history"]) > 0

    def test_crossover(self):
        p1 = {
            "name": "P1",
            "indicators": [{"type": "sma", "parameters": {"period": 20}}],
            "entry_signals": [{"type": "buy", "condition": {"logic": "AND", "conditions": []}}],
            "exit_signals": [],
            "risk_management": {"stop_loss": 50},
        }
        p2 = {
            "name": "P2",
            "indicators": [{"type": "ema", "parameters": {"period": 50}}],
            "entry_signals": [{"type": "buy", "condition": {"logic": "AND", "conditions": []}}],
            "exit_signals": [],
            "risk_management": {"stop_loss": 100},
        }
        child = self.mutator._crossover(p1, p2)
        assert child is not None


class TestMT5Generator:
    def setup_method(self):
        self.gen = MT5Generator()

    def test_generates_code(self):
        strategy = {
            "name": "TestStrategy",
            "indicators": [
                {"type": "sma", "parameters": {"period": 20}},
                {"type": "rsi", "parameters": {"period": 14, "overbought": 70, "oversold": 30}},
            ],
            "entry_signals": [{"type": "buy", "condition": {"logic": "AND", "conditions": []}}],
            "exit_signals": [],
            "risk_management": {"stop_loss": 50, "take_profit": 100},
        }
        code = self.gen.generate(strategy)
        assert len(code) > 100
        assert "#property" in code
        assert "OnInit" in code
        assert "OnTick" in code
        assert "CalculateLotSize" in code

    def test_includes_indicators(self):
        strategy = {
            "name": "IndTest",
            "indicators": [
                {"type": "macd", "parameters": {"fast_period": 12, "slow_period": 26, "signal_period": 9}},
            ],
            "entry_signals": [{"type": "buy", "condition": {"logic": "AND", "conditions": []}}],
            "exit_signals": [],
            "risk_management": {},
        }
        code = self.gen.generate(strategy)
        assert "iMACD" in code
        assert "macdMainBuffer" in code


class TestReportGenerator:
    def setup_method(self):
        self.gen = ReportGenerator(output_dir="/tmp/test_reports")

    def test_generates_report(self):
        results = {
            "metrics": {
                "total_return": 25.5, "sharpe_ratio": 1.5, "sortino_ratio": 2.0,
                "max_drawdown": 10.0, "win_rate": 60.0, "profit_factor": 1.8,
                "total_trades": 50, "winning_trades": 30, "losing_trades": 20,
                "avg_trade": 0.5, "avg_win": 1.2, "avg_loss": -0.6,
                "largest_win": 5.0, "largest_loss": -3.0,
                "calmar_ratio": 2.5, "omega_ratio": 1.5, "expectancy": 0.4,
                "recovery_factor": 2.0, "max_consecutive_wins": 5,
                "max_consecutive_losses": 3, "gross_profit": 36.0,
                "gross_loss": 12.0, "net_profit": 24.0,
            },
            "trades": [
                {"direction": "long", "entry_price": 1.1, "exit_price": 1.105,
                 "pnl": 50, "return_pct": 0.45, "is_win": True,
                 "entry_date": "2023-01-01T00:00:00", "exit_date": "2023-01-02T00:00:00"}
                for _ in range(10)
            ],
            "equity_curve": [10000 + i * 10 for i in range(100)],
            "symbol": "EURUSD",
            "timeframe": "H1",
        }
        path = self.gen.generate(results)
        assert os.path.exists(path)
        with open(path) as f:
            content = f.read()
        assert "EURUSD" in content
        assert "25.5" in content or "25.50" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
