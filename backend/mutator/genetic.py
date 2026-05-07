"""
Genetic Mutator - Evolves trading strategies using genetic algorithms.
Creates mutations, runs backtests in parallel, selects best performers.
"""
from __future__ import annotations
import copy
import random
import math
from typing import List, Dict, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np

from backtester.engine import BacktestEngine
from strategy.models import (
    StrategyIR, StrategyType, IndicatorType, Indicator,
    Signal, SignalType, Condition, ConditionGroup, ConditionOperator,
    RiskManagement
)


class GeneticMutator:
    """
    Genetic algorithm engine for evolving trading strategies.
    
    Operators:
    - Parameter mutation: perturb indicator parameters
    - Indicator swap: replace one indicator with another
    - Indicator add/remove: add or remove indicators
    - Condition modification: change entry/exit conditions
    - Risk parameter mutation: adjust stop loss, take profit, etc.
    - Crossover: combine two strategies
    """

    # Available indicators for mutation
    AVAILABLE_INDICATORS = [
        IndicatorType.SMA, IndicatorType.EMA, IndicatorType.RSI,
        IndicatorType.MACD, IndicatorType.BOLLINGER_BANDS, IndicatorType.ATR,
        IndicatorType.STOCHASTIC, IndicatorType.CCI, IndicatorType.ADX,
        IndicatorType.OBV, IndicatorType.VWAP,
    ]

    def __init__(self, initial_capital: float = 10000.0, commission: float = 0.001):
        self.engine = BacktestEngine()
        self.initial_capital = initial_capital
        self.commission = commission

    def evolve(
        self,
        base_strategy: dict,
        population_size: int = 20,
        generations: int = 10,
        objectives: List[str] = None,
        constraints: dict = None,
    ) -> Dict[str, Any]:
        """
        Evolve a strategy using genetic algorithm.
        
        Args:
            base_strategy: Starting strategy dict
            population_size: Number of strategies per generation
            generations: Number of generations to evolve
            objectives: Metrics to optimize (e.g. ["sharpe", "profit_factor"])
            constraints: Minimum requirements (e.g. {"min_trades": 30, "max_drawdown": 20})
            
        Returns:
            Dict with best strategies, evolution history, and statistics
        """
        objectives = objectives or ["sharpe", "profit_factor", "total_return"]
        constraints = constraints or {"min_trades": 10, "max_drawdown": 50}

        # Initialize population
        population = self._initialize_population(base_strategy, population_size)

        # Track evolution
        evolution_history = []
        all_results = []

        for gen in range(generations):
            # Evaluate fitness
            fitness_results = self._evaluate_population(population, objectives, constraints)

            # Sort by fitness (descending)
            fitness_results.sort(key=lambda x: x["fitness"], reverse=True)

            # Record generation stats
            gen_stats = {
                "generation": gen + 1,
                "best_fitness": fitness_results[0]["fitness"] if fitness_results else 0,
                "avg_fitness": np.mean([f["fitness"] for f in fitness_results]) if fitness_results else 0,
                "worst_fitness": fitness_results[-1]["fitness"] if fitness_results else 0,
                "best_strategy": fitness_results[0]["strategy"] if fitness_results else None,
                "best_metrics": fitness_results[0]["metrics"] if fitness_results else None,
                "n_valid": sum(1 for f in fitness_results if f.get("valid", True)),
                "n_total": len(fitness_results),
            }
            evolution_history.append(gen_stats)
            all_results.extend(fitness_results)

            # Check convergence
            if gen_stats["best_fitness"] > 0 and gen > 2:
                recent = [evolution_history[i]["best_fitness"] for i in range(max(0, gen - 3), gen + 1)]
                if max(recent) - min(recent) < 0.001:
                    break  # Converged

            # Selection + reproduction for next generation
            if gen < generations - 1:
                population = self._create_next_generation(
                    fitness_results, population_size, gen + 1, base_strategy
                )

        # Final evaluation of best
        all_results.sort(key=lambda x: x["fitness"], reverse=True)

        # Filter valid, non-overfitted strategies
        robust_results = self._filter_robust(all_results, constraints)

        return {
            "base_strategy": base_strategy,
            "best_strategies": all_results[:10] if all_results else [],
            "robust_strategies": robust_results[:5] if robust_results else [],
            "evolution_history": evolution_history,
            "total_evaluated": len(all_results),
            "generations_run": len(evolution_history),
            "objectives": objectives,
            "constraints": constraints,
        }

    def _initialize_population(self, base: dict, size: int) -> List[dict]:
        """Create initial population with random mutations of the base."""
        population = [copy.deepcopy(base)]  # Include original
        for i in range(1, size):
            mutant = self._random_mutate(base, mutation_rate=0.3 + (i / size) * 0.4)
            population.append(mutant)
        return population

    def _random_mutate(self, strategy: dict, mutation_rate: float = 0.3) -> dict:
        """Apply random mutations to a strategy."""
        mutant = copy.deepcopy(strategy)
        n_mutations = max(1, int(random.expovariate(1.0 / (mutation_rate * 5))))

        for _ in range(n_mutations):
            operator = random.choice([
                "perturb_params", "swap_indicator", "add_indicator",
                "remove_indicator", "mutate_risk", "mutate_conditions",
                "crossover_indicator",
            ])

            if operator == "perturb_params":
                mutant = self._mutate_indicator_params(mutant)
            elif operator == "swap_indicator":
                mutant = self._swap_indicator(mutant)
            elif operator == "add_indicator":
                mutant = self._add_indicator(mutant)
            elif operator == "remove_indicator":
                mutant = self._remove_indicator(mutant)
            elif operator == "mutate_risk":
                mutant = self._mutate_risk(mutant)
            elif operator == "mutate_conditions":
                mutant = self._mutate_conditions(mutant)

        mutant["mutated_from"] = strategy.get("name", "base")
        mutant["mutation_generation"] = strategy.get("mutation_generation", 0) + 1
        return mutant

    def _mutate_indicator_params(self, strategy: dict) -> dict:
        """Perturb indicator parameters."""
        indicators = strategy.get("indicators", [])
        if not indicators:
            return strategy

        idx = random.randint(0, len(indicators) - 1)
        indicator = indicators[idx]
        params = indicator.get("parameters", {})

        for key in params:
            if isinstance(params[key], (int, float)) and random.random() < 0.5:
                factor = random.uniform(0.7, 1.3)
                params[key] = params[key] * factor
                if key == "period" or isinstance(params[key], int):
                    params[key] = max(2, int(params[key]))
                else:
                    params[key] = round(params[key], 4)

        return strategy

    def _swap_indicator(self, strategy: dict) -> dict:
        """Replace a random indicator with a different one."""
        indicators = strategy.get("indicators", [])
        if not indicators:
            return strategy

        idx = random.randint(0, len(indicators) - 1)
        current_type = indicators[idx].get("type", "")
        available = [i for i in self.AVAILABLE_INDICATORS if i.value != current_type]

        if available:
            new_type = random.choice(available)
            defaults = {
                "sma": {"period": random.choice([10, 20, 50, 100, 200])},
                "ema": {"period": random.choice([9, 12, 20, 21, 50])},
                "rsi": {"period": random.choice([7, 9, 14, 21])},
                "macd": {"fast_period": random.choice([8, 12]), "slow_period": random.choice([21, 26]), "signal_period": random.choice([7, 9])},
                "bollinger_bands": {"period": random.choice([10, 20, 50]), "std_dev": random.choice([1.5, 2.0, 2.5, 3.0])},
                "atr": {"period": random.choice([7, 14, 21])},
                "stochastic": {"period": random.choice([5, 14, 21])},
                "cci": {"period": random.choice([10, 14, 20])},
                "adx": {"period": random.choice([10, 14, 21])},
                "obv": {},
                "vwap": {},
            }
            indicators[idx] = {
                "type": new_type.value,
                "parameters": defaults.get(new_type.value, {"period": 14})
            }

        return strategy

    def _add_indicator(self, strategy: dict) -> dict:
        """Add a new indicator."""
        indicators = strategy.get("indicators", [])
        current_types = {ind.get("type") for ind in indicators}
        available = [i for i in self.AVAILABLE_INDICATORS if i.value not in current_types]

        if available:
            new_type = random.choice(available)
            defaults = {
                "sma": {"period": random.choice([20, 50, 200])},
                "ema": {"period": random.choice([9, 21, 50])},
                "rsi": {"period": 14},
                "macd": {"fast_period": 12, "slow_period": 26, "signal_period": 9},
                "bollinger_bands": {"period": 20, "std_dev": 2.0},
                "atr": {"period": 14},
                "stochastic": {"period": 14},
                "cci": {"period": 20},
                "adx": {"period": 14},
                "obv": {},
                "vwap": {},
            }
            indicators.append({
                "type": new_type.value,
                "parameters": defaults.get(new_type.value, {"period": 14})
            })

        return strategy

    def _remove_indicator(self, strategy: dict) -> dict:
        """Remove a random indicator (keep at least one)."""
        indicators = strategy.get("indicators", [])
        if len(indicators) > 1:
            idx = random.randint(0, len(indicators) - 1)
            indicators.pop(idx)
        return strategy

    def _mutate_risk(self, strategy: dict) -> dict:
        """Mutate risk management parameters."""
        rm = strategy.get("risk_management", {})

        if random.random() < 0.5 and "stop_loss" in rm:
            factor = random.uniform(0.7, 1.5)
            if rm["stop_loss"]:
                rm["stop_loss"] = round(rm["stop_loss"] * factor, 2)

        if random.random() < 0.5 and "take_profit" in rm:
            factor = random.uniform(0.7, 1.5)
            if rm["take_profit"]:
                rm["take_profit"] = round(rm["take_profit"] * factor, 2)

        if random.random() < 0.3:
            rm["risk_per_trade"] = round(random.uniform(0.5, 3.0), 2)

        if random.random() < 0.3 and "trailing_stop" not in rm:
            rm["trailing_stop"] = round(random.uniform(10, 100), 2)

        return strategy

    def _mutate_conditions(self, strategy: dict) -> dict:
        """Modify entry/exit conditions."""
        entries = strategy.get("entry_signals", [])
        if entries and random.random() < 0.5:
            # Flip direction
            for sig in entries:
                if sig.get("type") == "buy":
                    sig["type"] = "sell"
                elif sig.get("type") == "sell":
                    sig["type"] = "buy"
        return strategy

    def _evaluate_population(
        self,
        population: List[dict],
        objectives: List[str],
        constraints: dict,
    ) -> List[Dict]:
        """Evaluate fitness of each strategy in the population."""
        results = []

        for i, strategy in enumerate(population):
            try:
                bt_result = self.engine.run(strategy=strategy)
                metrics = bt_result.get("metrics", {})

                # Check constraints
                valid = self._check_constraints(metrics, constraints)

                # Calculate fitness
                fitness = self._calculate_fitness(metrics, objectives) if valid else -1.0

                results.append({
                    "index": i,
                    "strategy": strategy,
                    "metrics": metrics,
                    "fitness": fitness,
                    "valid": valid,
                })
            except Exception:
                results.append({
                    "index": i,
                    "strategy": strategy,
                    "metrics": {},
                    "fitness": -1.0,
                    "valid": False,
                })

        return results

    def _check_constraints(self, metrics: dict, constraints: dict) -> bool:
        """Check if strategy meets constraints."""
        min_trades = constraints.get("min_trades", 0)
        if metrics.get("total_trades", 0) < min_trades:
            return False

        max_dd = constraints.get("max_drawdown", 100)
        if metrics.get("max_drawdown", 0) > max_dd:
            return False

        min_win_rate = constraints.get("min_win_rate", 0)
        if metrics.get("win_rate", 0) < min_win_rate:
            return False

        min_profit_factor = constraints.get("min_profit_factor", 0)
        if metrics.get("profit_factor", 0) < min_profit_factor:
            return False

        return True

    def _calculate_fitness(self, metrics: dict, objectives: List[str]) -> float:
        """Calculate composite fitness score from multiple objectives."""
        fitness = 0.0
        weights = {
            "sharpe": 0.3, "sortino": 0.1, "profit_factor": 0.2,
            "total_return": 0.2, "win_rate": 0.05, "calmar": 0.1,
            "expectancy": 0.05, "omega": 0.05,
        }

        for obj in objectives:
            obj_lower = obj.lower()
            weight = weights.get(obj_lower, 0.1)

            if obj_lower == "sharpe":
                fitness += weight * min(max(metrics.get("sharpe_ratio", 0) / 3.0, 0), 1)
            elif obj_lower == "sortino":
                fitness += weight * min(max(metrics.get("sortino_ratio", 0) / 3.0, 0), 1)
            elif obj_lower == "profit_factor":
                fitness += weight * min(max(metrics.get("profit_factor", 0) / 5.0, 0), 1)
            elif obj_lower == "total_return":
                ret = metrics.get("total_return", 0)
                fitness += weight * min(max(ret / 100.0, 0), 1) if ret > 0 else 0
            elif obj_lower == "win_rate":
                wr = metrics.get("win_rate", 0)
                fitness += weight * (wr / 100.0)
            elif obj_lower == "calmar":
                fitness += weight * min(max(metrics.get("calmar_ratio", 0) / 3.0, 0), 1)
            elif obj_lower == "expectancy":
                fitness += weight * min(max(metrics.get("expectancy", 0) / 100.0, 0), 1)
            elif obj_lower == "omega":
                fitness += weight * min(max(metrics.get("omega_ratio", 0) / 3.0, 0), 1)

        # Penalty for excessive drawdown
        dd = metrics.get("max_drawdown", 0)
        if dd > 30:
            fitness *= 0.7
        if dd > 50:
            fitness *= 0.4

        return round(fitness, 6)

    def _create_next_generation(
        self,
        fitness_results: List[dict],
        population_size: int,
        generation: int,
        base_strategy: dict,
    ) -> List[dict]:
        """Create next generation through selection, crossover, and mutation."""
        new_population = []

        # Elitism: keep top 10%
        n_elite = max(1, population_size // 10)
        for i in range(n_elite):
            if i < len(fitness_results):
                elite = copy.deepcopy(fitness_results[i]["strategy"])
                new_population.append(elite)

        # Fill rest with offspring
        valid_results = [r for r in fitness_results if r.get("valid", True) and r["fitness"] > 0]

        while len(new_population) < population_size:
            if len(valid_results) >= 2 and random.random() < 0.5:
                # Crossover
                parent1 = self._tournament_select(valid_results)
                parent2 = self._tournament_select(valid_results)
                child = self._crossover(parent1, parent2)
                child["mutation_generation"] = generation
                new_population.append(child)
            else:
                # Mutation
                if valid_results:
                    parent = self._tournament_select(valid_results)
                    child = self._random_mutate(parent, mutation_rate=0.2)
                    child["mutation_generation"] = generation
                    new_population.append(child)
                else:
                    # Random mutation of base
                    child = self._random_mutate(base_strategy, mutation_rate=0.4)
                    child["mutation_generation"] = generation
                    new_population.append(child)

        return new_population[:population_size]

    def _tournament_select(self, results: List[dict], k: int = 3) -> dict:
        """Tournament selection."""
        candidates = random.sample(results, min(k, len(results)))
        return max(candidates, key=lambda x: x["fitness"])["strategy"]

    def _crossover(self, parent1: dict, parent2: dict) -> dict:
        """Combine two strategies (crossover indicators and risk params)."""
        child = copy.deepcopy(parent1)

        # Crossover indicators
        p2_indicators = parent2.get("indicators", [])
        if p2_indicators and random.random() < 0.5:
            n = min(len(child.get("indicators", [])), len(p2_indicators))
            if n > 0:
                idx = random.randint(0, n - 1)
                child.setdefault("indicators", [])[idx] = copy.deepcopy(p2_indicators[idx])

        # Crossover risk management
        p2_rm = parent2.get("risk_management", {})
        if p2_rm and random.random() < 0.5:
            child.setdefault("risk_management", {}).update({
                k: v for k, v in p2_rm.items()
                if k in ("stop_loss", "take_profit", "trailing_stop", "risk_per_trade")
            })

        return child

    def _filter_robust(self, results: List[dict], constraints: dict) -> List[dict]:
        """Filter out potentially overfitted strategies."""
        robust = []
        for r in results:
            metrics = r.get("metrics", {})
            if not metrics:
                continue

            # Criteria for robustness
            n_trades = metrics.get("total_trades", 0)
            sharpe = metrics.get("sharpe_ratio", 0)
            profit_factor = metrics.get("profit_factor", 0)
            max_dd = metrics.get("max_drawdown", 100)

            # Need sufficient trades
            if n_trades < constraints.get("min_trades", 10):
                continue

            # Sharpe should be positive
            if sharpe <= 0:
                continue

            # Profit factor should be > 1
            if profit_factor <= 1:
                continue

            # Drawdown should be reasonable
            if max_dd > constraints.get("max_drawdown", 50):
                continue

            robust.append(r)

        return robust
