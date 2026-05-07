import React from 'react';
import { useStore } from '../stores/appStore';

export const Sidebar = () => {
  const { sessions, activeSessionId, newSession, setActiveSession, isConnected } = useStore();

  return (
    <div className="w-60 bg-bg-secondary border-r border-border flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b border-border">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-xl">📈</span>
          <h1 className="font-bold text-accent-blue text-sm">Trading Strategy AI</h1>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-accent-green' : 'bg-accent-red'}`} />
          <span className="text-text-muted">{isConnected ? 'Connected' : 'Disconnected'}</span>
        </div>
      </div>

      {/* New Session */}
      <div className="p-3">
        <button onClick={newSession}
          className="w-full py-2 bg-accent-blue/10 border border-accent-blue/30 rounded-lg text-accent-blue text-sm font-medium hover:bg-accent-blue/20 transition-colors">
          + New Session
        </button>
      </div>

      {/* Sessions List */}
      <div className="flex-1 overflow-y-auto px-3 space-y-1">
        {sessions.map(session => (
          <button key={session.id}
            onClick={() => setActiveSession(session.id)}
            className={`w-full text-left p-2 rounded-lg text-sm transition-colors ${session.id === activeSessionId ? 'bg-accent-blue/10 text-accent-blue border border-accent-blue/20' : 'text-text-secondary hover:bg-bg-tertiary'}`}>
            <div className="truncate font-medium">{session.title}</div>
            <div className="text-xs text-text-muted">{new Date(session.createdAt).toLocaleDateString()}</div>
          </button>
        ))}
        {sessions.length === 0 && (
          <div className="text-text-muted text-xs text-center py-4">No sessions yet</div>
        )}
      </div>

      {/* Footer */}
      <div className="p-3 border-t border-border text-xs text-text-muted text-center">
        v1.0.0 | crazycompanyinc
      </div>
    </div>
  );
};
