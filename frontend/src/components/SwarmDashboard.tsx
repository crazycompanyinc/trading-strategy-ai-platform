import React from 'react';
import { useStore } from '../stores/appStore';
import type { SwarmTask } from '../stores/appStore';

const statusColors: Record<string, string> = {
  pending: 'bg-text-muted/30',
  running: 'bg-accent-blue/20 border-accent-blue/40',
  completed: 'bg-accent-green/20 border-accent-green/40',
  error: 'bg-accent-red/20 border-accent-red/40',
  cancelled: 'bg-text-muted/20',
};

const statusIcons: Record<string, string> = {
  pending: '○',
  running: '◐',
  completed: '✓',
  error: '✗',
  cancelled: '⊘',
};

const roleLabels: Record<string, string> = {
  researcher: '🔬 Researcher',
  strategist: '📐 Strategist',
  backtester: '📊 Backtester',
  genetic_mutator: '🧬 Genetic Mutator',
  mt5_generator: '💻 MT5 Generator',
  reporter: '📝 Reporter',
};

const TaskCard = ({ task }: { task: SwarmTask }) => {
  const colorClass = statusColors[task.status] || statusColors.pending;
  const icon = statusIcons[task.status] || '○';
  const label = roleLabels[task.role] || task.role;

  return (
    <div className={`rounded-lg border p-3 ${colorClass} transition-all duration-300`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium">{label}</span>
        <span className="text-xs">{icon} {task.status}</span>
      </div>
      {task.status === 'running' && (
        <div className="w-full bg-bg-secondary rounded-full h-1.5 mb-2">
          <div
            className="bg-accent-blue h-1.5 rounded-full transition-all duration-500"
            style={{ width: `${Math.min(task.progress * 100, 100)}%` }}
          />
        </div>
      )}
      {task.message && (
        <div className="text-xs text-text-muted truncate">{task.message}</div>
      )}
      {task.duration !== undefined && task.duration !== null && (
        <div className="text-xs text-text-muted mt-1">{task.duration}s</div>
      )}
    </div>
  );
};

export const SwarmDashboard = () => {
  const { swarmState } = useStore();

  if (!swarmState) return null;

  const tasks = Object.values(swarmState.tasks || {});
  const runningCount = tasks.filter(t => t.status === 'running').length;
  const completedCount = tasks.filter(t => t.status === 'completed').length;
  const totalCount = tasks.length;

  return (
    <div className="bg-bg-secondary border border-border rounded-xl p-4 mb-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-accent-blue font-semibold text-sm">🤖 Agent Swarm</span>
          <span className="text-xs text-text-muted">
            {completedCount}/{totalCount} agents done
            {runningCount > 0 && ` · ${runningCount} running`}
          </span>
        </div>
        <div className="text-xs text-text-muted">
          {swarmState.duration?.toFixed(1)}s
        </div>
      </div>

      {/* Overall progress */}
      <div className="w-full bg-bg-primary rounded-full h-2 mb-4">
        <div
          className="bg-gradient-to-r from-accent-blue to-accent-green h-2 rounded-full transition-all duration-500"
          style={{ width: `${Math.min(swarmState.overall_progress * 100, 100)}%` }}
        />
      </div>

      {/* Agent grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
        {tasks.map(task => (
          <TaskCard key={task.role} task={task} />
        ))}
      </div>

      {/* Results summary */}
      {swarmState.is_complete && (
        <div className="mt-3 pt-3 border-t border-border">
          <div className="flex gap-4 text-xs">
            {swarmState.backtest_results && (
              <span className="text-accent-green">✓ Backtest</span>
            )}
            {swarmState.mutation_results && (
              <span className="text-accent-purple">✓ Evolution</span>
            )}
            {swarmState.mt5_code && (
              <span className="text-accent-blue">✓ MT5 Code</span>
            )}
            {swarmState.strategy && (
              <span className="text-accent-yellow">✓ Strategy</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
