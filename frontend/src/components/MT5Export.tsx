import React from 'react';
import { useStore } from '../stores/appStore';

export const MT5Export = () => {
  const { mt5Code, currentStrategy, exportMT5 } = useStore();

  const handleExport = () => {
    if (currentStrategy) exportMT5(currentStrategy);
  };

  const handleCopy = () => {
    if (mt5Code) navigator.clipboard.writeText(mt5Code);
  };

  const handleDownload = () => {
    if (!mt5Code) return;
    const blob = new Blob([mt5Code], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${currentStrategy?.name || 'Strategy'}.mq5`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="h-full flex flex-col">
      <div className="p-4 border-b border-border flex justify-between items-center">
        <div>
          <h2 className="text-lg font-bold text-accent-yellow">📝 MT5 Code</h2>
          <p className="text-text-muted text-xs">Generated MQL5 Expert Advisor</p>
        </div>
        <div className="flex gap-2">
          <button onClick={handleExport} disabled={!currentStrategy}
            className="px-3 py-1.5 bg-bg-secondary border border-border rounded text-sm hover:border-accent-blue/50 disabled:opacity-30">
            Generate
          </button>
          <button onClick={handleCopy} disabled={!mt5Code}
            className="px-3 py-1.5 bg-bg-secondary border border-border rounded text-sm hover:border-accent-blue/50 disabled:opacity-30">
            Copy
          </button>
          <button onClick={handleDownload} disabled={!mt5Code}
            className="px-3 py-1.5 bg-accent-yellow text-black rounded text-sm font-medium hover:bg-accent-yellow/80 disabled:opacity-30">
            Download .mq5
          </button>
        </div>
      </div>
      <div className="flex-1 overflow-auto p-4">
        {mt5Code ? (
          <pre className="font-mono text-xs leading-relaxed text-text-primary whitespace-pre-wrap bg-bg-primary border border-border rounded-lg p-4">
            {mt5Code}
          </pre>
        ) : (
          <div className="flex items-center justify-center h-full text-text-secondary">
            <div className="text-center">
              <div className="text-4xl mb-3">📝</div>
              <p>Generate MT5 code from your strategy</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
