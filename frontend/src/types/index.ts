export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  images?: string[];
  timestamp: string;
  strategy?: StrategyIR;
  backtestResults?: BacktestResult;
  mt5Code?: string;
  mutationResults?: MutationResult;
}

export interface StrategyIR {
  name: string;
  description: string;
  type: string;
  instruments: string[];
  timeframes: string[];
  indicators: Indicator[];
  entry_signals: Signal[];
  exit_signals: Signal[];
  risk_management: RiskManagement;
  [key: string]: any;
}

export interface Indicator {
  type: string;
  parameters: Record<string, any>;
}

export interface Signal {
  type: string;
  condition: any;
  confidence: number;
}

export interface RiskManagement {
  stop_loss?: number;
  take_profit?: number;
  trailing_stop?: number;
  max_position_size?: number;
  risk_per_trade?: number;
  max_drawdown_limit?: number;
  [key: string]: any;
}

export interface BacktestResult {
  metrics: Record<string, number>;
  trades: Trade[];
  equity_curve: number[];
  symbol: string;
  timeframe: string;
  [key: string]: any;
}

export interface Trade {
  direction: string;
  entry_price: number;
  exit_price: number;
  pnl: number;
  return_pct: number;
  is_win: boolean;
}

export interface MutationResult {
  best_strategies: MutationCandidate[];
  evolution_history: GenerationStats[];
  total_evaluated: number;
}

export interface MutationCandidate {
  strategy: StrategyIR;
  metrics: Record<string, number>;
  fitness: number;
  valid: boolean;
}

export interface GenerationStats {
  generation: number;
  best_fitness: number;
  avg_fitness: number;
  n_valid: number;
}

export interface Session {
  id: string;
  title: string;
  messages: Message[];
  createdAt: string;
  updatedAt: string;
}
