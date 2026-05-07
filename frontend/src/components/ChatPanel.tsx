import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useStore } from '../stores/appStore';
import { Message } from '../types';

const TypingIndicator = () => (
  <div className="chat-message flex gap-3 p-4">
    <div className="w-8 h-8 rounded-full bg-accent-blue/20 flex items-center justify-center text-accent-blue text-sm font-bold shrink-0">AI</div>
    <div className="typing-indicator pt-2"><span></span><span></span><span></span></div>
  </div>
);

const MessageBubble = ({ msg }: { msg: Message }) => {
  const isUser = msg.role === 'user';
  return (
    <div className={`chat-message flex gap-3 p-4 ${isUser ? 'flex-row-reverse' : ''}`}>
      <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold shrink-0 ${isUser ? 'bg-accent-purple/20 text-accent-purple' : 'bg-accent-blue/20 text-accent-blue'}`}>
        {isUser ? 'U' : 'AI'}
      </div>
      <div className={`max-w-[75%] rounded-lg p-4 ${isUser ? 'bg-accent-blue/10 border border-accent-blue/20' : 'bg-bg-secondary border border-border'}`}>
        {msg.images && msg.images.length > 0 && (
          <div className="flex gap-2 mb-3 flex-wrap">
            {msg.images.map((img, i) => (
              <img key={i} src={img} alt={`Upload ${i}`} className="max-w-[200px] max-h-[150px] rounded-lg border border-border" />
            ))}
          </div>
        )}
        <div className="markdown-body text-sm">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
        </div>
        <div className="text-text-muted text-xs mt-2">{new Date(msg.timestamp).toLocaleTimeString()}</div>
      </div>
    </div>
  );
};

export const ChatPanel = () => {
  const [input, setInput] = useState('');
  const [images, setImages] = useState<string[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { messages, isProcessing, sendMessage } = useStore();

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isProcessing]);

  const handleSend = () => {
    if (!input.trim() && images.length === 0) return;
    sendMessage(input.trim(), images.length > 0 ? images : undefined);
    setInput('');
    setImages([]);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
  };

  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;
    Array.from(files).forEach(file => {
      const reader = new FileReader();
      reader.onload = (ev) => {
        if (ev.target?.result) {
          setImages(prev => [...prev, ev.target!.result as string]);
        }
      };
      reader.readAsDataURL(file);
    });
    e.target.value = '';
  };

  const removeImage = (idx: number) => setImages(prev => prev.filter((_, i) => i !== idx));

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-2">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-text-secondary">
            <div className="text-6xl mb-4">📈</div>
            <h2 className="text-xl font-semibold text-accent-blue mb-2">Trading Strategy AI</h2>
            <p className="text-center max-w-md">Describe your trading idea in natural language. I'll research it, build a strategy, backtest it, and generate MT5 code.</p>
            <div className="mt-6 grid grid-cols-2 gap-3 text-sm">
              <div className="bg-bg-secondary border border-border rounded-lg p-3 cursor-pointer hover:border-accent-blue/50 transition-colors"
                onClick={() => setInput('Create a trend following strategy using EMA crossover on EURUSD H1 with RSI filter')}>
                <div className="text-accent-blue font-medium">📊 Trend Following</div>
                <div className="text-text-muted text-xs mt-1">EMA crossover + RSI filter</div>
              </div>
              <div className="bg-bg-secondary border border-border rounded-lg p-3 cursor-pointer hover:border-accent-blue/50 transition-colors"
                onClick={() => setInput('Mean reversion strategy on GBPUSD using Bollinger Bands and RSI on H4')}>
                <div className="text-accent-green font-medium">🔄 Mean Reversion</div>
                <div className="text-text-muted text-xs mt-1">Bollinger Bands + RSI</div>
              </div>
              <div className="bg-bg-secondary border border-border rounded-lg p-3 cursor-pointer hover:border-accent-blue/50 transition-colors"
                onClick={() => setInput('Breakout strategy on XAUUSD daily with ATR-based stop loss and volume confirmation')}>
                <div className="text-accent-yellow font-medium">💥 Breakout</div>
                <div className="text-text-muted text-xs mt-1">ATR stop + Volume</div>
              </div>
              <div className="bg-bg-secondary border border-border rounded-lg p-3 cursor-pointer hover:border-accent-blue/50 transition-colors"
                onClick={() => setInput('Scalping strategy on EURUSD M15 using MACD and stochastic with tight stop loss')}>
                <div className="text-accent-purple font-medium">⚡ Scalping</div>
                <div className="text-text-muted text-xs mt-1">MACD + Stochastic</div>
              </div>
            </div>
          </div>
        )}
        {messages.map(msg => <MessageBubble key={msg.id} msg={msg} />)}
        {isProcessing && <TypingIndicator />}
        <div ref={messagesEndRef} />
      </div>

      {/* Image previews */}
      {images.length > 0 && (
        <div className="px-4 pb-2 flex gap-2 flex-wrap">
          {images.map((img, i) => (
            <div key={i} className="relative">
              <img src={img} alt="" className="w-16 h-16 object-cover rounded border border-border" />
              <button onClick={() => removeImage(i)} className="absolute -top-1 -right-1 w-5 h-5 bg-accent-red rounded-full text-white text-xs flex items-center justify-center">×</button>
            </div>
          ))}
        </div>
      )}

      {/* Input */}
      <div className="border-t border-border p-4">
        <div className="flex gap-2 items-end">
          <button onClick={() => fileInputRef.current?.click()}
            className="p-2 rounded-lg bg-bg-secondary border border-border hover:border-accent-blue/50 transition-colors text-text-secondary"
            title="Upload image">
            📎
          </button>
          <input ref={fileInputRef} type="file" accept="image/*" multiple onChange={handleImageUpload} className="hidden" />
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Describe your trading idea..."
            className="flex-1 bg-bg-secondary border border-border rounded-lg p-3 text-sm resize-none focus:outline-none focus:border-accent-blue/50 min-h-[44px] max-h-[120px]"
            rows={1}
          />
          <button onClick={handleSend}
            disabled={!input.trim() && images.length === 0}
            className="p-3 rounded-lg bg-accent-blue text-white font-medium hover:bg-accent-blue/80 disabled:opacity-30 disabled:cursor-not-allowed transition-colors">
            Send
          </button>
        </div>
      </div>
    </div>
  );
};
