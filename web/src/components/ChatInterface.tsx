'use client';

import { useState, useRef, useEffect } from 'react';
import { Send, Loader2, Bot, User, AlertTriangle, GitBranch, GitPullRequest, CircleDot, ExternalLink } from 'lucide-react';
import { VoiceInput } from './VoiceInput';

interface GitHubLink {
  url: string | null;
  number: string | null;
}

interface GitHubIntegration {
  branch: string | null;
  issue: GitHubLink | null;
  pr: GitHubLink | null;
}

interface Session {
  id: string;
  name: string;
  status: string;
  github?: GitHubIntegration | null;
}

interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  status?: string;
}

interface ChatInterfaceProps {
  session: Session;
  onError?: (message: string) => void;
  isMobile?: boolean;
}

export function ChatInterface({ session, onError, isMobile = false }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Fetch messages when session changes
  useEffect(() => {
    fetchMessages();
  }, [session.id]);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const fetchMessages = async () => {
    try {
      const response = await fetch(`/api/chat/${session.id}/messages`);
      if (response.ok) {
        const data = await response.json();
        setMessages(data.messages);
      } else {
        onError?.('Failed to load messages');
      }
    } catch (error) {
      console.error('Failed to fetch messages:', error);
      onError?.('Failed to fetch messages');
    }
  };

  const sendMessage = async () => {
    if (!input.trim() || loading) return;

    const userMessage: Message = {
      id: `temp-${Date.now()}`,
      role: 'user',
      content: input,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setLoading(true);
    setStreaming(true);

    try {
      // Use streaming endpoint
      const response = await fetch(`/api/chat/${session.id}/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: session.id, content: userMessage.content }),
      });

      if (!response.ok) throw new Error('Failed to send message');

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      let assistantMessage: Message = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: '',
        timestamp: new Date().toISOString(),
        status: 'streaming',
      };

      setMessages((prev) => [...prev, assistantMessage]);

      while (reader) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.content) {
                assistantMessage = {
                  ...assistantMessage,
                  content: assistantMessage.content + data.content,
                };
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantMessage.id ? assistantMessage : m
                  )
                );
              }
            } catch {
              // Skip non-JSON lines
            }
          }
        }
      }

      // Mark as complete
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantMessage.id ? { ...m, status: 'complete' } : m
        )
      );
    } catch (error) {
      console.error('Failed to send message:', error);
      const errorMsg = 'Failed to get response. Please try again.';
      // Notify parent via callback
      onError?.(errorMsg);
      // Add error message to chat
      setMessages((prev) => [
        ...prev,
        {
          id: `error-${Date.now()}`,
          role: 'system',
          content: errorMsg,
          timestamp: new Date().toISOString(),
        },
      ]);
    } finally {
      setLoading(false);
      setStreaming(false);
    }
  };

  const handleVoiceTranscription = (text: string) => {
    setInput(text);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const formatTime = (timestamp: string) => {
    try {
      return new Date(timestamp).toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return '';
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full min-h-0">
      {/* Header - hide on mobile since we show it in the main header */}
      {!isMobile && (
        <div className="p-4 border-b border-edge-subtle glass-panel flex-shrink-0">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div className="min-w-0">
              <h2 className="font-semibold text-content-primary flex items-center gap-2">
                <span className="truncate">{session.name}</span>
                <span className="w-2 h-2 rounded-full bg-neon-cyan animate-pulse flex-shrink-0" />
              </h2>
              <p className="text-xs text-content-tertiary font-mono mt-0.5 truncate">
                id:{session.id}
              </p>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              {/* GitHub Links */}
              {session.github && (
                <div className="flex items-center gap-2 flex-wrap">
                  {session.github.branch && (
                    <span className="flex items-center gap-1.5 text-xs text-content-secondary px-2 py-1 
                                     bg-surface-tertiary rounded-lg border border-edge-subtle">
                      <GitBranch className="w-3.5 h-3.5 flex-shrink-0" />
                      <span className="font-mono truncate max-w-[120px]">{session.github.branch}</span>
                    </span>
                  )}
                  {session.github.issue?.url && (
                    <a
                      href={session.github.issue.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1.5 text-xs text-violet hover:text-violet/80 
                                 px-2 py-1 bg-violet/10 rounded-lg border border-violet/20
                                 transition-colors group"
                    >
                      <CircleDot className="w-3.5 h-3.5 flex-shrink-0" />
                      <span>Issue {session.github.issue.number}</span>
                      <ExternalLink className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                    </a>
                  )}
                  {session.github.pr?.url && (
                    <a
                      href={session.github.pr.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1.5 text-xs text-emerald-400 hover:text-emerald-300 
                                 px-2 py-1 bg-emerald-400/10 rounded-lg border border-emerald-400/20
                                 transition-colors group"
                    >
                      <GitPullRequest className="w-3.5 h-3.5 flex-shrink-0" />
                      <span>PR {session.github.pr.number}</span>
                      <ExternalLink className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                    </a>
                  )}
                </div>
              )}
              <span className="text-xs text-content-tertiary px-2 py-1 bg-surface-tertiary rounded-lg border border-edge-subtle">
                {messages.length} messages
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-3 md:p-6 min-h-0">
        {messages.length === 0 ? (
          <div className="h-full flex items-center justify-center">
            <div className="text-center max-w-sm px-4">
              <div className="w-16 h-16 md:w-20 md:h-20 rounded-2xl bg-gradient-to-br from-surface-secondary to-surface-tertiary 
                            border border-edge-subtle flex items-center justify-center mx-auto mb-4 md:mb-6
                            shadow-inner-glow">
                <Bot className="w-7 h-7 md:w-9 md:h-9 text-content-tertiary" />
              </div>
              <p className="text-content-secondary mb-2 text-sm md:text-base">Start a conversation</p>
              <p className="text-content-tertiary text-xs md:text-sm">
                Type a message or use voice input to begin
              </p>
            </div>
          </div>
        ) : (
          <div className="space-y-4 md:space-y-6 max-w-4xl mx-auto">
            {messages.map((message, index) => (
              <div
                key={message.id}
                className={`flex gap-2 md:gap-4 message-bubble ${
                  message.role === 'user' ? 'flex-row-reverse' : ''
                }`}
                style={{ animationDelay: `${index * 50}ms` }}
              >
                {/* Avatar */}
                <div className={`flex-shrink-0 w-7 h-7 md:w-9 md:h-9 rounded-lg md:rounded-xl flex items-center justify-center
                  ${message.role === 'user' 
                    ? 'bg-neon-cyan/20 text-neon-cyan border border-neon-cyan/30' 
                    : message.role === 'system'
                    ? 'bg-amber/20 text-amber border border-amber/30'
                    : 'bg-violet/20 text-violet border border-violet/30'
                  }`}
                >
                  {message.role === 'user' ? (
                    <User className="w-3.5 h-3.5 md:w-4 md:h-4" />
                  ) : message.role === 'system' ? (
                    <AlertTriangle className="w-3.5 h-3.5 md:w-4 md:h-4" />
                  ) : (
                    <Bot className="w-3.5 h-3.5 md:w-4 md:h-4" />
                  )}
                </div>

                {/* Message Content */}
                <div className={`flex-1 max-w-[85%] md:max-w-[80%] ${message.role === 'user' ? 'text-right' : ''}`}>
                  <div
                    className={`inline-block rounded-xl md:rounded-2xl px-3 py-2 md:px-5 md:py-3 text-left text-sm md:text-base
                      ${message.role === 'user'
                        ? 'bg-gradient-to-br from-neon-cyan/20 to-neon-cyan/10 border border-neon-cyan/30 text-content-primary'
                        : message.role === 'system'
                        ? 'bg-amber/10 border border-amber/30 text-amber'
                        : 'bg-surface-elevated border border-edge-subtle text-content-primary'
                      }`}
                  >
                    <p className="whitespace-pre-wrap leading-relaxed">{message.content}</p>
                    {message.status === 'streaming' && (
                      <span className="inline-block w-2 h-4 md:h-5 bg-neon-cyan ml-1 typing-cursor" />
                    )}
                  </div>
                  <div className={`mt-1 md:mt-1.5 text-[10px] md:text-xs text-content-tertiary ${message.role === 'user' ? 'text-right' : ''}`}>
                    {formatTime(message.timestamp)}
                  </div>
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input */}
      <div className="p-3 md:p-4 border-t border-edge-subtle glass-panel flex-shrink-0">
        <div className="flex items-end gap-2 md:gap-3 max-w-4xl mx-auto">
          <div className="flex-1 relative min-w-0">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type a message..."
              rows={1}
              className="w-full px-3 py-3 md:px-5 md:py-4 border border-edge-medium rounded-xl md:rounded-2xl 
                         bg-surface-secondary text-content-primary text-sm md:text-base
                         focus:ring-2 focus:ring-neon-cyan/30 focus:border-neon-cyan/50
                         placeholder:text-content-tertiary resize-none transition-all
                         outline-none"
              style={{ minHeight: isMobile ? '44px' : '56px', maxHeight: '150px' }}
            />
          </div>
          
          <VoiceInput onTranscription={handleVoiceTranscription} />
          
          <button
            onClick={sendMessage}
            disabled={!input.trim() || loading}
            className="p-3 md:p-4 bg-neon-cyan text-surface-primary rounded-xl md:rounded-2xl
                       hover:shadow-glow disabled:opacity-30 disabled:cursor-not-allowed
                       disabled:hover:shadow-none transition-all active:scale-95 flex-shrink-0"
          >
            {loading ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Send className="w-5 h-5" />
            )}
          </button>
        </div>
        
        {/* Typing hint - hide on mobile */}
        {!isMobile && (
          <div className="flex items-center justify-center gap-4 mt-3 text-xs text-content-tertiary">
            <span className="flex items-center gap-1.5">
              <kbd className="px-1.5 py-0.5 bg-surface-tertiary border border-edge-subtle rounded text-[10px] font-mono">
                Enter
              </kbd>
              to send
            </span>
            <span className="flex items-center gap-1.5">
              <kbd className="px-1.5 py-0.5 bg-surface-tertiary border border-edge-subtle rounded text-[10px] font-mono">
                Shift + Enter
              </kbd>
              for new line
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
