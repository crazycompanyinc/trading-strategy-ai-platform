import { create } from 'zustand';
import type { Message, Session, BacktestResult, StrategyIR, MutationResult } from '../types';

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
  connect: () => void;
  disconnect: () => void;
  sendMessage: (content: string, images?: string[]) => void;
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
    const { ws, isConnected } = get();
    const msg: Message = {
      id: crypto.randomUUID(), role: 'user', content, images,
      timestamp: new Date().toISOString(),
    };
    get().addMessage(msg);
    set({ isProcessing: true });
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
    set({ sessions, activeSessionId: sid, messages: [], currentStrategy: null, backtestResults: null, mutationResults: null, mt5Code: null });
    get().disconnect();
    get().connect();
  },

  setActiveSession: (id) => { set({ activeSessionId: id }); get().disconnect(); get().connect(); },
  setCurrentStrategy: (s) => set({ currentStrategy: s }),
  setBacktestResults: (r) => set({ backtestResults: r }),
  setMutationResults: (r) => set({ mutationResults: r }),
  setMT5Code: (code) => set({ mt5Code: code }),
  setProcessing: (v) => set({ isProcessing: v }),

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
