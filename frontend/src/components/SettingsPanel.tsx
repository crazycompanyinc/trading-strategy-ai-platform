import React, { useState, useEffect } from 'react';

interface SettingsPanelProps {
  onNavigateToChat: () => void;
}

export const SettingsPanel: React.FC<SettingsPanelProps> = ({ onNavigateToChat }) => {
  const [apiKey, setApiKey] = useState('');
  const [model, setModel] = useState('openrouter/owl-alpha');
  const [backendStatus, setBackendStatus] = useState<'running' | 'stopped' | 'unknown'>('unknown');
  const [pythonStatus, setPythonStatus] = useState<{ found: boolean; path: string }>({ found: false, path: '' });
  const [logs, setLogs] = useState<string[]>([]);
  const [errors, setErrors] = useState<string[]>([]);
  const [saved, setSaved] = useState(false);
  const [validating, setValidating] = useState(false);
  const [testResult, setTestResult] = useState<string>('');

  useEffect(() => {
    // Load config
    if (window.electronAPI) {
      window.electronAPI.getConfig().then((config: any) => {
        if (config?.openrouterApiKey) setApiKey(config.openrouterApiKey);
        if (config?.openrouterModel) setModel(config.openrouterModel);
      });

      window.electronAPI.getBackendStatus().then((s: any) => setBackendStatus(s.status));
      window.electronAPI.checkPython().then((p: any) => setPythonStatus(p));

      // Listen for backend events
      window.electronAPI.onBackendLog((msg: string) => {
        setLogs(prev => [...prev.slice(-50), msg]);
      });
      window.electronAPI.onBackendError((msg: string) => {
        setErrors(prev => [...prev.slice(-20), msg]);
      });
      window.electronAPI.onBackendStatus((status: string) => {
        setBackendStatus(status as 'running' | 'stopped' | 'unknown');
      });
    }
  }, []);

  const handleSave = async () => {
    if (window.electronAPI) {
      await window.electronAPI.saveConfig({
        openrouterApiKey: apiKey.trim(),
        openrouterModel: model.trim(),
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
      const status = await window.electronAPI.getBackendStatus();
      setBackendStatus(status.status as 'running' | 'stopped' | 'unknown');
    }
  };

  const handleTestConnection = async () => {
    setValidating(true);
    setTestResult('');
    try {
      // Quick test: try to reach the backend
      const res = await fetch('http://localhost:8000/health', { signal: AbortSignal.timeout(3000) });
      if (res.ok) {
        const data = await res.json();
        setTestResult('✅ Backend is running and healthy!');
      } else {
        setTestResult('⚠️ Backend responded with error: ' + res.status);
      }
    } catch (e: any) {
      if (e.name === 'TimeoutError' || e.name === 'AbortError') {
        setTestResult('❌ Cannot connect to backend. Make sure Python is installed.');
      } else {
        setTestResult('❌ Connection failed: ' + e.message);
      }
    }
    setValidating(false);
  };

  const handleRestartBackend = async () => {
    if (window.electronAPI) {
      await window.electronAPI.stopBackend();
      await new Promise(r => setTimeout(r, 1000));
      await window.electronAPI.startBackend();
      const status = await window.electronAPI.getBackendStatus();
      setBackendStatus(status.status as 'running' | 'stopped' | 'unknown');
    }
  };

  return (
    <div className="h-full overflow-y-auto p-6 space-y-6">
      <div>
        <h2 className="text-xl font-bold text-accent-blue mb-1">⚙️ Settings</h2>
        <p className="text-text-muted text-sm">Configure your AI trading platform</p>
      </div>

      {/* Status */}
      <div className="bg-bg-secondary border border-border rounded-lg p-4">
        <h3 className="text-sm font-semibold text-accent-blue mb-3">System Status</h3>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <span className="text-text-muted">Backend: </span>
            <span className={backendStatus === 'running' ? 'text-accent-green' : 'text-accent-red'}>
              {backendStatus === 'running' ? '● Running' : '○ Stopped'}
            </span>
          </div>
          <div>
            <span className="text-text-muted">Python: </span>
            <span className={pythonStatus.found ? 'text-accent-green' : 'text-accent-red'}>
              {pythonStatus.found ? `● Found (${pythonStatus.path})` : '○ Not found'}
            </span>
          </div>
        </div>
        <div className="flex gap-2 mt-3">
          <button onClick={handleTestConnection} disabled={validating}
            className="px-3 py-1.5 bg-accent-blue/10 border border-accent-blue/30 rounded text-accent-blue text-xs font-medium hover:bg-accent-blue/20 disabled:opacity-30">
            {validating ? 'Testing...' : '🧪 Test Connection'}
          </button>
          <button onClick={handleRestartBackend}
            className="px-3 py-1.5 bg-accent-yellow/10 border border-accent-yellow/30 rounded text-accent-yellow text-xs font-medium hover:bg-accent-yellow/20">
            🔄 Restart Backend
          </button>
        </div>
        {testResult && (
          <div className="mt-2 p-2 bg-bg-primary rounded text-sm">{testResult}</div>
        )}
      </div>

      {/* API Key */}
      <div className="bg-bg-secondary border border-border rounded-lg p-4">
        <h3 className="text-sm font-semibold text-accent-blue mb-3">🤖 AI Model Configuration</h3>
        <p className="text-text-muted text-xs mb-4">
          The AI agent needs an OpenRouter API key to understand your trading ideas.
          Get a free key at <a href="https://openrouter.ai/keys" target="_blank" rel="noopener noreferrer" className="text-accent-blue underline">openrouter.ai/keys</a>
        </p>

        <div className="space-y-3">
          <div>
            <label className="text-text-muted text-xs block mb-1">OpenRouter API Key</label>
            <input
              type="password"
              value={apiKey}
              onChange={e => setApiKey(e.target.value)}
              placeholder="sk-or-v1-..."
              className="w-full bg-bg-primary border border-border rounded-lg p-3 text-sm font-mono focus:outline-none focus:border-accent-blue/50"
            />
            <p className="text-text-muted text-xs mt-1">
              {apiKey ? '✅ Key configured (masked for security)' : '⚠️ No key configured - AI agent will use basic keyword matching'}
            </p>
          </div>

          <div>
            <label className="text-text-muted text-xs block mb-1">Model</label>
            <select
              value={model}
              onChange={e => setModel(e.target.value)}
              className="w-full bg-bg-primary border border-border rounded-lg p-3 text-sm focus:outline-none focus:border-accent-blue/50"
            >
              <option value="openrouter/owl-alpha">OWL Alpha (default)</option>
              <option value="anthropic/claude-sonnet-4">Claude Sonnet 4</option>
              <option value="anthropic/claude-haiku-4">Claude Haiku 4</option>
              <option value="openai/gpt-4o">GPT-4o</option>
              <option value="openai/gpt-4o-mini">GPT-4o Mini</option>
              <option value="google/gemini-2.0-flash">Gemini 2.0 Flash</option>
              <option value="deepseek/deepseek-chat">DeepSeek Chat</option>
              <option value="meta-llama/llama-4-maverick">Llama 4 Maverick</option>
            </select>
          </div>

          <button onClick={handleSave}
            className="w-full py-2.5 bg-accent-blue text-white rounded-lg font-medium hover:bg-accent-blue/80 transition-colors">
            {saved ? '✅ Saved & Backend Restarted!' : '💾 Save & Restart Backend'}
          </button>
        </div>
      </div>

      {/* Quick Start */}
      {!apiKey && (
        <div className="bg-accent-yellow/5 border border-accent-yellow/20 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-accent-yellow mb-2">🚀 Quick Start Guide</h3>
          <ol className="text-sm text-text-secondary space-y-1 list-decimal list-inside">
            <li>Go to <a href="https://openrouter.ai/keys" target="_blank" rel="noopener noreferrer" className="text-accent-blue underline">openrouter.ai/keys</a> and create a free account</li>
            <li>Copy your API key and paste it above</li>
            <li>Click "Save & Restart Backend"</li>
            <li>Go to the Chat tab and describe your trading idea!</li>
          </ol>
        </div>
      )}

      {/* Backend Logs */}
      {(logs.length > 0 || errors.length > 0) && (
        <div className="bg-bg-secondary border border-border rounded-lg p-4">
          <h3 className="text-sm font-semibold text-accent-blue mb-2">📋 Backend Logs</h3>
          <div className="bg-bg-primary rounded p-3 max-h-40 overflow-y-auto font-mono text-xs">
            {logs.map((log, i) => (
              <div key={`log-${i}`} className="text-text-muted">{log}</div>
            ))}
            {errors.map((err, i) => (
              <div key={`err-${i}`} className="text-accent-red">{err}</div>
            ))}
            {logs.length === 0 && errors.length === 0 && (
              <div className="text-text-muted">No logs yet...</div>
            )}
          </div>
        </div>
      )}

      {/* Next Step */}
      {apiKey && backendStatus === 'running' && (
        <div className="bg-accent-green/5 border border-accent-green/20 rounded-lg p-4 text-center">
          <p className="text-accent-green font-medium mb-2">✅ Everything is configured!</p>
          <button onClick={onNavigateToChat}
            className="px-6 py-2 bg-accent-green text-white rounded-lg font-medium hover:bg-accent-green/80 transition-colors">
            💬 Go to Chat
          </button>
        </div>
      )}
    </div>
  );
};
