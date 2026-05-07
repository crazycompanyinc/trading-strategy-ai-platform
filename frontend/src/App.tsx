import React, { useEffect, useState, useCallback } from 'react';
import { useStore } from './stores/appStore';
import { Sidebar } from './components/Sidebar';
import { ChatPanel } from './components/ChatPanel';
import { BacktestReport } from './components/BacktestReport';
import { MutationPanel } from './components/MutationPanel';
import { MT5Export } from './components/MT5Export';
import { StrategyViewer } from './components/StrategyViewer';
import { SettingsPanel } from './components/SettingsPanel';

type Tab = 'chat' | 'backtest' | 'mutation' | 'mt5' | 'strategy' | 'settings';

const tabs: { id: Tab; label: string; icon: string }[] = [
  { id: 'chat', label: 'Chat', icon: '💬' },
  { id: 'strategy', label: 'Strategy', icon: '📋' },
  { id: 'backtest', label: 'Backtest', icon: '📊' },
  { id: 'mutation', label: 'Mutate', icon: '🧬' },
  { id: 'mt5', label: 'MT5 Code', icon: '📝' },
  { id: 'settings', label: 'Settings', icon: '⚙️' },
];

const App = () => {
  const [activeTab, setActiveTab] = useState<Tab>('chat');
  const { connect, currentStrategy, runBacktest, isProcessing } = useStore();

  useEffect(() => {
    connect();
  }, []);

  const handleQuickBacktest = () => {
    if (currentStrategy) {
      runBacktest(currentStrategy);
      setActiveTab('backtest');
    }
  };

  return (
    <div className="flex h-screen bg-bg-primary text-text-primary">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="flex border-b border-border bg-bg-secondary">
          {tabs.map(tab => (
            <button key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${activeTab === tab.id ? 'border-accent-blue text-accent-blue' : 'border-transparent text-text-secondary hover:text-text-primary'}`}>
              <span className="mr-2">{tab.icon}</span>
              {tab.label}
            </button>
          ))}
          {currentStrategy && activeTab !== 'settings' && (
            <div className="ml-auto flex items-center px-4 gap-2">
              <button onClick={handleQuickBacktest} disabled={isProcessing}
                className="px-3 py-1 bg-accent-green/10 border border-accent-green/30 rounded text-accent-green text-xs font-medium hover:bg-accent-green/20 disabled:opacity-30">
                ⚡ Quick Backtest
              </button>
            </div>
          )}
        </div>
        <div className="flex-1 overflow-hidden">
          {activeTab === 'chat' && <ChatPanel />}
          {activeTab === 'strategy' && <StrategyViewer />}
          {activeTab === 'backtest' && <BacktestReport />}
          {activeTab === 'mutation' && <MutationPanel />}
          {activeTab === 'mt5' && <MT5Export />}
          {activeTab === 'settings' && <SettingsPanel onNavigateToChat={() => setActiveTab('chat')} />}
        </div>
      </div>
    </div>
  );
};

export default App;
