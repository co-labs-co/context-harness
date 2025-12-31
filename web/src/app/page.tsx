'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { SessionList } from '@/components/SessionList';
import { ChatInterface } from '@/components/ChatInterface';
import { MessageSquare, Sparkles, Terminal, AlertCircle, X, RefreshCw, WifiOff } from 'lucide-react';

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
  created_at: string;
  updated_at: string;
  compaction_cycle: number;
  active_work: string | null;
  github?: GitHubIntegration | null;
}

interface Toast {
  id: string;
  type: 'error' | 'success' | 'info';
  message: string;
}

const STORAGE_KEY = 'contextharness_active_session';

export default function Home() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSession, setActiveSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [showNewSessionModal, setShowNewSessionModal] = useState(false);
  const sessionListRef = useRef<{ focusNewSession: () => void } | null>(null);

  // Add toast notification
  const addToast = useCallback((type: Toast['type'], message: string) => {
    const id = `toast-${Date.now()}`;
    setToasts(prev => [...prev, { id, type, message }]);
    // Auto-remove after 5 seconds
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 5000);
  }, []);

  // Remove toast
  const removeToast = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  // Restore active session from localStorage
  useEffect(() => {
    const savedSessionId = localStorage.getItem(STORAGE_KEY);
    if (savedSessionId && sessions.length > 0) {
      const savedSession = sessions.find(s => s.id === savedSessionId);
      if (savedSession && !activeSession) {
        setActiveSession(savedSession);
      }
    }
  }, [sessions, activeSession]);

  // Save active session to localStorage
  useEffect(() => {
    if (activeSession) {
      localStorage.setItem(STORAGE_KEY, activeSession.id);
    }
  }, [activeSession]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // ⌘+N or Ctrl+N: New session
      if ((e.metaKey || e.ctrlKey) && e.key === 'n') {
        e.preventDefault();
        setShowNewSessionModal(true);
      }
      // ⌘+R or Ctrl+R: Refresh sessions (when not in input)
      if ((e.metaKey || e.ctrlKey) && e.key === 'r' && document.activeElement?.tagName !== 'TEXTAREA' && document.activeElement?.tagName !== 'INPUT') {
        e.preventDefault();
        fetchSessions();
        addToast('info', 'Refreshing sessions...');
      }
      // Escape: Close modals, deselect
      if (e.key === 'Escape') {
        if (showNewSessionModal) {
          setShowNewSessionModal(false);
        }
      }
      // ⌘+1-9: Quick switch to session by index
      if ((e.metaKey || e.ctrlKey) && e.key >= '1' && e.key <= '9') {
        const index = parseInt(e.key) - 1;
        if (sessions[index]) {
          e.preventDefault();
          setActiveSession(sessions[index]);
          addToast('info', `Switched to ${sessions[index].name}`);
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [showNewSessionModal, sessions, addToast]);

  const fetchSessions = async () => {
    setError(null);
    try {
      const response = await fetch('/api/sessions');
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      const data = await response.json();
      setSessions(data.sessions);
      
      // Auto-select first session if none selected and no saved session
      if (data.sessions.length > 0 && !activeSession) {
        const savedSessionId = localStorage.getItem(STORAGE_KEY);
        const savedSession = savedSessionId ? data.sessions.find((s: Session) => s.id === savedSessionId) : null;
        setActiveSession(savedSession || data.sessions[0]);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch sessions';
      setError(message);
      addToast('error', message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSessions();
  }, []);

  const handleSelectSession = (session: Session) => {
    setActiveSession(session);
  };

  const handleCreateSession = async (name: string) => {
    try {
      const response = await fetch('/api/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name }),
      });
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP ${response.status}`);
      }
      
      const newSession = await response.json();
      setSessions(prev => [newSession, ...prev]);
      setActiveSession(newSession);
      setShowNewSessionModal(false);
      addToast('success', `Created session "${name}"`);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create session';
      addToast('error', message);
    }
  };

  return (
    <div className="flex h-screen bg-surface-primary">
      {/* Toast Notifications */}
      <div className="fixed top-4 right-4 z-50 space-y-2">
        {toasts.map(toast => (
          <div
            key={toast.id}
            className={`flex items-center gap-3 px-4 py-3 rounded-xl shadow-lg animate-in
              ${toast.type === 'error' ? 'bg-red-500/90 text-white' : ''}
              ${toast.type === 'success' ? 'bg-emerald-500/90 text-white' : ''}
              ${toast.type === 'info' ? 'bg-surface-elevated border border-edge-subtle text-content-primary' : ''}
            `}
          >
            {toast.type === 'error' && <AlertCircle className="w-4 h-4 flex-shrink-0" />}
            <span className="text-sm">{toast.message}</span>
            <button
              onClick={() => removeToast(toast.id)}
              className="ml-2 opacity-70 hover:opacity-100 transition-opacity"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>

      {/* Sidebar */}
      <aside className="w-80 border-r border-edge-subtle glass-panel flex flex-col">
        {/* Header */}
        <div className="p-5 border-b border-edge-subtle">
          <div className="flex items-center gap-3">
            <div className="relative">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-neon-cyan/20 to-violet/20 
                            flex items-center justify-center border border-neon-cyan/30">
                <Terminal className="w-5 h-5 text-neon-cyan" />
              </div>
              <div className={`absolute -top-1 -right-1 w-3 h-3 rounded-full shadow-glow-sm
                ${error ? 'bg-red-500' : 'bg-neon-cyan animate-pulse'}`} />
            </div>
            <div className="flex-1">
              <h1 className="text-lg font-semibold text-content-primary flex items-center gap-2">
                ContextHarness
              </h1>
              <p className="text-xs text-content-tertiary font-mono">
                session://manager
              </p>
            </div>
            {/* Refresh button */}
            <button
              onClick={() => { fetchSessions(); addToast('info', 'Refreshing...'); }}
              className="p-2 text-content-tertiary hover:text-content-primary hover:bg-surface-tertiary 
                         rounded-lg transition-colors"
              title="Refresh sessions (⌘+R)"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {/* Error State */}
        {error && !loading && (
          <div className="p-4 m-3 rounded-xl bg-red-500/10 border border-red-500/30">
            <div className="flex items-center gap-2 text-red-400 text-sm">
              <WifiOff className="w-4 h-4" />
              <span>Connection error</span>
            </div>
            <p className="text-xs text-content-tertiary mt-1">{error}</p>
            <button
              onClick={fetchSessions}
              className="mt-2 text-xs text-neon-cyan hover:underline"
            >
              Try again
            </button>
          </div>
        )}

        {/* Sessions List */}
        <SessionList
          ref={sessionListRef}
          sessions={sessions}
          activeSession={activeSession}
          loading={loading}
          onSelectSession={handleSelectSession}
          onCreateSession={handleCreateSession}
          showNewSessionForm={showNewSessionModal}
          onToggleNewSession={setShowNewSessionModal}
        />
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col bg-surface-primary">
        {activeSession ? (
          <ChatInterface session={activeSession} onError={(msg) => addToast('error', msg)} />
        ) : (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center max-w-md mx-auto px-6">
              {/* Animated icon */}
              <div className="relative mb-8 inline-block">
                <div className="w-24 h-24 rounded-2xl bg-gradient-to-br from-surface-secondary to-surface-tertiary 
                              border border-edge-subtle flex items-center justify-center mx-auto
                              shadow-inner-glow">
                  <MessageSquare className="w-10 h-10 text-content-tertiary" />
                </div>
                {/* Orbiting sparkle */}
                <div className="absolute top-0 right-0 animate-float">
                  <Sparkles className="w-5 h-5 text-neon-cyan opacity-60" />
                </div>
              </div>
              
              <h2 className="text-2xl font-semibold text-content-primary mb-3">
                No Session Selected
              </h2>
              <p className="text-content-secondary leading-relaxed">
                Select a session from the sidebar or create a new one to start working
              </p>
              
              {/* Keyboard shortcuts */}
              <div className="mt-8 space-y-2">
                <div className="flex items-center justify-center gap-2 text-content-tertiary text-sm">
                  <kbd className="px-2 py-1 bg-surface-tertiary border border-edge-subtle rounded text-xs font-mono">
                    ⌘
                  </kbd>
                  <span>+</span>
                  <kbd className="px-2 py-1 bg-surface-tertiary border border-edge-subtle rounded text-xs font-mono">
                    N
                  </kbd>
                  <span className="ml-2">New session</span>
                </div>
                <div className="flex items-center justify-center gap-2 text-content-tertiary text-sm">
                  <kbd className="px-2 py-1 bg-surface-tertiary border border-edge-subtle rounded text-xs font-mono">
                    ⌘
                  </kbd>
                  <span>+</span>
                  <kbd className="px-2 py-1 bg-surface-tertiary border border-edge-subtle rounded text-xs font-mono">
                    1-9
                  </kbd>
                  <span className="ml-2">Quick switch</span>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
