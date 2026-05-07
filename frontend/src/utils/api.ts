const API_BASE = 'http://localhost:8000';

export async function chat(message: string, images?: string[], sessionId?: string) {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, images, session_id: sessionId }),
  });
  return res.json();
}

export async function runBacktest(strategy: any, params?: any) {
  const res = await fetch(`${API_BASE}/api/backtest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ strategy, ...params }),
  });
  return res.json();
}

export async function runMutation(strategy: any, config?: any) {
  const res = await fetch(`${API_BASE}/api/mutate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ strategy, ...config }),
  });
  return res.json();
}

export async function runRobustness(strategy: any) {
  const res = await fetch(`${API_BASE}/api/robustness`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ strategy }),
  });
  return res.json();
}

export async function exportMT5(strategy: any) {
  const res = await fetch(`${API_BASE}/api/export/mt5`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(strategy),
  });
  return res.json();
}

export async function generateReport(results: any) {
  const res = await fetch(`${API_BASE}/api/report`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(results),
  });
  return res.json();
}
