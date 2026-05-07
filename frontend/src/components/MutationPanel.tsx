import React, { useState } from 'react';
import { useStore } from '../stores/appStore';

export const MutationPanel = () => {
  const { mutationResults, currentStrategy, isProcessing, runMutation } = useStore();
  const [config, setConfig] = useState({
    population_size: 20,
    generations: 10,
    objectives: 'sharpe,profit_factor,total_return',
  });

  const handleMutate = () => {
    if (!currentStrategy) return;
    runMutation(currentStrategy, {
      population_size: config.population_size,
      generations: config.generations,
      objectives: config.objectives.split(',').map(s => s.trim()),
    });
  };

  return (
    <div className="h-full overflow-y-auto p-6 space-y-6">
      <div>
        <h2 className="text-xl font-bold text-accent-purple mb-1">🧬 Strategy Mutation</h2>
        <p className="text-text-muted text-sm">Evolve your strategy using genetic algorithms</p>
      </div>

      {/* Config */}
      <div className="bg-bg-secondary border border-border rounded-lg p-4 space-y-4">
        <h3 className="text-sm font-semibold text-accent-blue">Mutation Configuration</h3>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="text-text-muted text-xs block mb-1">Population Size</label>
            <input type="number" value={config.population_size}
              onChange={e => setConfig(c => ({ ...c, population_size: +e.target.value }))}
              className="w-full bg-bg-primary border border-border rounded p-2 text-sm focus:outline-none focus:border-accent-blue/50" />
          </div>
          <div>
            <label className="text-text-muted text-xs block mb-1">Generations</label>
            <input type="number" value={config.generations}
              onChange={e => setConfig(c => ({ ...c, generations: +e.target.value }))}
              className="w-full bg-bg-primary border border-border rounded p-2 text-sm focus:outline-none focus:border-accent-blue/50" />
          </div>
          <div>
            <label className="text-text-muted text-xs block mb-1">Objectives (comma-separated)</label>
            <input type="text" value={config.objectives}
              onChange={e => setConfig(c => ({ ...c, objectives: e.target.value }))}
              className="w-full bg-bg-primary border border-border rounded p-2 text-sm focus:outline-none focus:border-accent-blue/50" />
          </div>
        </div>
        <button onClick={handleMutate} disabled={!currentStrategy || isProcessing}
          className="px-6 py-2 bg-accent-purple text-white rounded-lg font-medium hover:bg-accent-purple/80 disabled:opacity-30 disabled:cursor-not-allowed transition-colors">
          {isProcessing ? '🧬 Evolving...' : '🧬 Mutate Strategy'}
        </button>
        {!currentStrategy && <p className="text-accent-yellow text-sm">⚠️ Create a strategy first via chat</p>}
      </div>

      {/* Results */}
      {mutationResults && (
        <>
          {/* Evolution Chart */}
          <div className="bg-bg-secondary border border-border rounded-lg p-4">
            <h3 className="text-sm font-semibold text-accent-blue mb-3">Evolution Progress</h3>
            <div className="space-y-2">
              {mutationResults.evolution_history?.map((gen: any) => (
                <div key={gen.generation} className="flex items-center gap-3">
                  <span className="text-text-muted text-xs w-20">Gen {gen.generation}</span>
                  <div className="flex-1 bg-bg-primary rounded-full h-4 overflow-hidden">
                    <div className="h-full bg-gradient-to-r from-accent-purple to-accent-blue rounded-full transition-all"
                      style={{ width: `${Math.min(100, (gen.best_fitness / Math.max(1, mutationResults.evolution_history?.[mutationResults.evolution_history.length - 1]?.best_fitness)) * 100)}%` }} />
                  </div>
                  <span className="text-xs text-accent-blue font-mono w-16 text-right">{gen.best_fitness.toFixed(4)}</span>
                  <span className="text-xs text-text-muted w-16 text-right">{gen.n_valid}/{gen.n_total} valid</span>
                </div>
              ))}
            </div>
          </div>

          {/* Best Strategies */}
          <div className="bg-bg-secondary border border-border rounded-lg p-4">
            <h3 className="text-sm font-semibold text-accent-blue mb-3">Top Mutated Strategies</h3>
            <div className="space-y-3">
              {mutationResults.best_strategies?.slice(0, 10).map((candidate: any, i: number) => (
                <div key={i} className={`p-3 rounded-lg border ${i === 0 ? 'border-accent-green/50 bg-accent-green/5' : 'border-border'}`}>
                  <div className="flex justify-between items-center mb-2">
                    <span className="font-medium text-sm">#{i + 1} {candidate.strategy?.name || 'Mutated'}</span>
                    <span className="text-accent-blue font-mono text-sm">Fitness: {candidate.fitness?.toFixed(4)}</span>
                  </div>
                  <div className="grid grid-cols-4 gap-2 text-xs">
                    <div><span className="text-text-muted">Return:</span> <span className={candidate.metrics?.total_return > 0 ? 'text-accent-green' : 'text-accent-red'}>{candidate.metrics?.total_return?.toFixed(2)}%</span></div>
                    <div><span className="text-text-muted">Sharpe:</span> <span className="text-accent-blue">{candidate.metrics?.sharpe_ratio?.toFixed(4)}</span></div>
                    <div><span className="text-text-muted">Win Rate:</span> <span className="text-accent-blue">{candidate.metrics?.win_rate?.toFixed(2)}%</span></div>
                    <div><span className="text-text-muted">Trades:</span> <span className="text-accent-blue">{candidate.metrics?.total_trades}</span></div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {!mutationResults && !isProcessing && (
        <div className="flex items-center justify-center h-40 text-text-secondary">
          <div className="text-center">
            <div className="text-4xl mb-3">🧬</div>
            <p>Configure and run mutation to evolve your strategy</p>
          </div>
        </div>
      )}
    </div>
  );
};
