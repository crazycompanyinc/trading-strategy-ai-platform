import { create } from 'zustand';
import type { Message, Session, BacktestResult, StrategyIR, MutationResult } from '../types';

export interface SwarmTask {
  role: string;
  status: 'pending' | 'running' | 'completed' | 'error' | 'cancelled';
  progress: number;
  message: string;
  error?: string;
  duration?: number;
}

export interface SwarmState {
  session_id: string;
  query: string;
  overall_progress: number;
  is_complete: boolean;
  tasks: Record<string, SwarmTask>;
  strategy: any | null;
  backtest_results: any | null;
  mutation_results: any | null;
  robustness_results: any | null;
  mt5_code: boolean;
  report_path: string | null;
  final_response: string;
  duration: number;
}

interface AppState {
  sessions: Session[];
  activeSessionId: string | null;
  messages: Message[];
  isConnected: boolean;
  isProcessing: boolean;
  ws: WebSocket | null;
  currentStrategy: StrategyIR | null;
  backtestResults: BacktestResult | null;
  mutationResults: MutationResult | null;
  mt5Code: string | null;
  robustnessResults: any | null;
  // Swarm state
  swarmState: SwarmState | null;
  swarmEnabled: boolean;
  connect: () => void;
  disconnect: () => void;
  sendMessage: (content: string, images?: string[]) => void;
  sendSwarmMessage: (content: string) => void;
  newSession: () => void;
  setActiveSession: (id: string) => void;
  addMessage: (msg: Message) => void;
  setCurrentStrategy: (s: StrategyIR | null) => void;
  setBacktestResults: (r: BacktestResult | null) => void;
  setMutationResults: (r: MutationResult | null) => void;
  setMT5Code: (code: string | null) => void;
  runBacktest: (strategy: any) => void;
  runMutation: (strategy: any, config?: any) => void;
  runRobustness: (strategy: any) => void;
  exportMT5: (strategy: any) => void;
  setProcessing: (v: boolean) => void;
  setSwarmState: (s: SwarmState | null) => void;
  setSwarmEnabled: (v: boolean) => void;
}

const SESSIONS_KEY = 'trading_sessions';

function loadSessions(): Session[] {
  try {
    const stored = localStorage.getItem(SESSIONS_KEY);
    return stored ? JSON.parse(stored) : [];
  } catch { return []; }
}

function saveSessions(sessions: Session[]) {
  localStorage.setItem(SESSIONS_KEY, JSON.stringify(sessions));
}

export const useStore = create<AppState>((set, get) => ({
  sessions: loadSessions(),
  activeSessionId: null,
  messages: [],
  isConnected: false,
  isProcessing: false,
  ws: null,
  currentStrategy: null,
  backtestResults: null,
  mutationResults: null,
  mt5Code: null,
  robustnessResults: null,
  swarmState: null,
  swarmEnabled: true, // Default to swarm mode

  connect: () => {
    const sid = get().activeSessionId || crypto.randomUUID();
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//localhost:8000/ws/${sid}`;
    try {
      const ws = new WebSocket(wsUrl);
      ws.onopen = () => set({ isConnected: true, ws, activeSessionId: sid });
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          if (data.type === 'response') {
            const msg: Message = {
              id: crypto.randomUUID(), role: 'assistant',
              content: data.response || '', timestamp: new Date().toISOString(),
              strategy: data.strategy, backtestResults: data.backtest_results,
              mt5Code: data.mt5_code,
            };
            get().addMessage(msg);
            if (data.strategy) set({ currentStrategy: data.strategy });
            if (data.backtest_results) set({ backtestResults: data.backtest_results });
            if (data.mt5_code) set({ mt5Code: data.mt5_code });
            set({ isProcessing: false });

          } else if (data.type === 'swarm_progress') {
            set({ swarmState: data.state, isProcessing: true });

          } else if (data.type === 'swarm_complete') {
            const msg: Message = {
              id: crypto.randomUUID(), role: 'assistant',
              content: data.response || '', timestamp: new Date().toISOString(),
              strategy: data.strategy, backtestResults: data.backtest_results,
              mt5Code: data.mt5_code,
            };
            get().addMessage(msg);
            if (data.strategy) set({ currentStrategy: data.strategy });
            if (data.backtest_results) set({ backtestResults: data.backtest_results });
            if (data.mt5_code) set({ mt5Code: data.mt5_code });
            if (data.state) set({ swarmState: data.state });
            set({ isProcessing: false });

          } else if (data.type === 'backtest_results') {
            set({ backtestResults: data.results, isProcessing: false });

          } else if (data.type === 'mutation_results') {
            set({ mutationResults: data.mutations, isProcessing: false });
          }
        } catch (e) { console.error('WS message error:', e); }
      };
      ws.onclose = () => set({ isConnected: false, ws: null });
      ws.onerror = () => set({ isConnected: false, ws: null });
    } catch (e) { console.error('WS connection error:', e); }
  },

  disconnect: () => {
    const { ws } = get();
    if (ws) ws.close();
    set({ isConnected: false, ws: null });
  },

  sendMessage: (content, images) => {
    const { ws, isConnected, swarmEnabled } = get();

    // Add user message
    const msg: Message = {
      id: crypto.randomUUID(), role: 'user', content, images,
      timestamp: new Date().toISOString(),
    };
    get().addMessage(msg);
    set({ isProcessing: true, swarmState: null });

    if (swarmEnabled) {
      // Use swarm mode
      if (ws && isConnected) {
        ws.send(JSON.stringify({ type: 'swarm', content, images: images || [] }));
      } else {
        // Fallback: use SSE streaming via fetch
        get().sendSwarmMessage(content);
      }
    } else {
      // Use regular chat mode
      if (ws && isConnected) {
        ws.send(JSON.stringify({ type: 'chat', content, images: images || [] }));
      } else {
        fetch('http://localhost:8000/api/chat', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: content, images: images || [] }),
        })
          .then(r => r.json())
          .then(data => {
            const responseMsg: Message = {
              id: crypto.randomUUID(), role: 'assistant',
              content: data.response || '', timestamp: new Date().toISOString(),
              strategy: data.strategy, backtestResults: data.backtest_results,
              mt5Code: data.mt5_code,
            };
            get().addMessage(responseMsg);
            if (data.strategy) set({ currentStrategy: data.strategy });
            if (data.backtest_results) set({ backtestResults: data.backtest_results });
            if (data.mt5_code) set({ mt5Code: data.mt5_code });
            set({ isProcessing: false });
          })
          .catch(err => { console.error('API error:', err); set({ isProcessing: false }); });
      }
    }
  },

  sendSwarmMessage: async (content) => {
    // SSE streaming fallback when WebSocket is not available
    try {
      const response = await fetch('http://localhost:8000/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: content }),
      });

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const event = JSON.parse(line.slice(6));
                if (event.type === 'progress' && event.state) {
                  set({ swarmState: event.state, isProcessing: true });
                } else if (event.type === 'complete') {
                  const msg: Message = {
                    id: crypto.randomUUID(), role: 'assistant',
                    content: event.response || '', timestamp: new Date().toISOString(),
                    strategy: event.strategy, backtestResults: event.backtest_results,
                    mt5Code: event.mt5_code,
                  };
                  get().addMessage(msg);
                  if (event.strategy) set({ currentStrategy: event.strategy });
                  if (event.backtest_results) set({ backtestResults: event.backtest_results });
                  if (event.mt5_code) set({ mt5Code: event.mt5_code });
                  if (event.state) set({ swarmState: event.state });
                  set({ isProcessing: false });
                }
              } catch (e) {
                console.error('SSE parse error:', e);
              }
            }
          }
        }
      }
    } catch (err) {
      console.error('SSE error:', err);
      set({ isProcessing: false });
    }
  },

  addMessage: (msg) => set((state) => ({ messages: [...state.messages, msg] })),

  newSession: () => {
    const sid = crypto.randomUUID();
    const session: Session = {
      id: sid, title: `Session ${new Date().toLocaleDateString()}`,
      messages: [], createdAt: new Date().toISOString(), updatedAt: new Date().toISOString(),
    };
    const sessions = [session, ...get().sessions];
    saveSessions(sessions);
    set({
      sessions, activeSessionId: sid, messages: [],
      currentStrategy: null, backtestResults: null, mutationResults: null,
      mt5Code: null, swarmState: null,
    });
    get().disconnect();
    get().connect();
  },

  setActiveSession: (id) => { set({ activeSessionId: id }); get().disconnect(); get().connect(); },
  setCurrentStrategy: (s) => set({ currentStrategy: s }),
  setBacktestResults: (r) => set({ backtestResults: r }),
  setMutationResults: (r) => set({ mutationResults: r }),
  setMT5Code: (code) => set({ mt5Code: code }),
  setProcessing: (v) => set({ isProcessing: v }),
  setSwarmState: (s) => set({ swarmState: s }),
  setSwarmEnabled: (v) => set({ swarmEnabled: v }),

  runBacktest: (strategy) => {
    const { ws, isConnected } = get();
    set({ isProcessing: true });
    if (ws && isConnected) ws.send(JSON.stringify({ type: 'backtest', strategy }));
  },

  runMutation: (strategy, config) => {
    const { ws, isConnected } = get();
    set({ isProcessing: true });
    if (ws && isConnected) ws.send(JSON.stringify({ type: 'mutate', strategy, ...config }));
  },

  runRobustness: (strategy) => {
    set({ isProcessing: true });
    fetch('http://localhost:8000/api/robustness', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ strategy }),
    }).then(r => r.json()).then(data => {
      set({ robustnessResults: data.results, isProcessing: false });
    }).catch(() => set({ isProcessing: false }));
  },

  exportMT5: (strategy) => {
    fetch('http://localhost:8000/api/export/mt5', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(strategy),
    }).then(r => r.json()).then(data => {
      if (data.code) set({ mt5Code: data.code });
    }).catch(console.error);
  },
}));
