'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { SessionList } from '@/components/SessionList';
import { ChatInterface } from '@/components/ChatInterface';
import { SettingsModal } from '@/components/SettingsModal';
import { MessageSquare, Sparkles, Terminal, AlertCircle, X, RefreshCw, WifiOff, Menu, ChevronLeft, Settings } from 'lucide-react';

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
const THEME_STORAGE_KEY = 'selectedTheme';
const DEFAULT_MODEL_STORAGE_KEY = 'contextharness_default_model';

export default function Home() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSession, setActiveSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [showNewSessionModal, setShowNewSessionModal] = useState(false);
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const [currentTheme, setCurrentTheme] = useState('solarized_light');
  const [defaultModel, setDefaultModel] = useState('');
  const sessionListRef = useRef<{ focusNewSession: () => void } | null>(null);

  // Detect mobile viewport
  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768);
      // Close sidebar on desktop resize
      if (window.innerWidth >= 768) {
        setSidebarOpen(false);
      }
    };
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  // Load saved theme and default model on mount
  useEffect(() => {
    const savedTheme = localStorage.getItem(THEME_STORAGE_KEY) || 'solarized_light';
    if (savedTheme !== currentTheme) {
      setCurrentTheme(savedTheme);
    }
    
    const savedModel = localStorage.getItem(DEFAULT_MODEL_STORAGE_KEY) || '';
    if (savedModel !== defaultModel) {
      setDefaultModel(savedModel);
    }
  }, []);

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

  // Handle theme change (save to localStorage)
  const handleThemeChange = useCallback((theme: string) => {
    setCurrentTheme(theme);
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  }, []);

  // Handle default model change
  const handleDefaultModelChange = useCallback((modelId: string) => {
    setDefaultModel(modelId);
    localStorage.setItem(DEFAULT_MODEL_STORAGE_KEY, modelId);
    addToast('success', 'Default model updated');
  }, [addToast]);

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
      // ⌘+, or Ctrl+,: Open settings
      if ((e.metaKey || e.ctrlKey) && e.key === ',') {
        e.preventDefault();
        setShowSettingsModal(true);
      }
      // ⌘+R or Ctrl+R: Refresh sessions (when not in input)
      if ((e.metaKey || e.ctrlKey) && e.key === 'r' && document.activeElement?.tagName !== 'TEXTAREA' && document.activeElement?.tagName !== 'INPUT') {
        e.preventDefault();
        fetchSessions();
        addToast('info', 'Refreshing sessions...');
      }
      // Escape: Close modals, sidebar, deselect
      if (e.key === 'Escape') {
        if (showSettingsModal) {
          setShowSettingsModal(false);
        } else if (showNewSessionModal) {
          setShowNewSessionModal(false);
        } else if (sidebarOpen) {
          setSidebarOpen(false);
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
  }, [showNewSessionModal, showSettingsModal, sidebarOpen, sessions, addToast]);

  const fetchSessions = async (silent = false) => {
    if (!silent) setError(null);
    try {
      const response = await fetch('/api/sessions');
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      const data = await response.json();
      setSessions(data.sessions);
      
      // Update active session with fresh data if it exists
      if (activeSession) {
        const updatedActiveSession = data.sessions.find((s: Session) => s.id === activeSession.id);
        if (updatedActiveSession) {
          // Only update if something changed (avoid unnecessary re-renders)
          if (JSON.stringify(updatedActiveSession) !== JSON.stringify(activeSession)) {
            setActiveSession(updatedActiveSession);
          }
        }
      }
      
      // Auto-select first session if none selected and no saved session
      if (data.sessions.length > 0 && !activeSession) {
        const savedSessionId = localStorage.getItem(STORAGE_KEY);
        const savedSession = savedSessionId ? data.sessions.find((s: Session) => s.id === savedSessionId) : null;
        setActiveSession(savedSession || data.sessions[0]);
      }
    } catch (err) {
      if (!silent) {
        const message = err instanceof Error ? err.message : 'Failed to fetch sessions';
        setError(message);
        addToast('error', message);
      }
    } finally {
      if (!silent) setLoading(false);
    }
  };

  // Initial fetch
  useEffect(() => {
    fetchSessions();
  }, []);

  // Poll for session updates every 5 seconds when there's an active session
  // This catches changes made by the agent (commits, PRs, etc.)
  useEffect(() => {
    if (!activeSession) return;
    
    const pollInterval = setInterval(() => {
      fetchSessions(true); // silent = true, don't show loading/errors
    }, 5000);
    
    return () => clearInterval(pollInterval);
  }, [activeSession?.id]);

  const handleSelectSession = (session: Session) => {
    setActiveSession(session);
    // Close sidebar on mobile when session is selected
    if (isMobile) {
      setSidebarOpen(false);
    }
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
    <div className="flex h-screen bg-surface-primary overflow-hidden">
      {/* Toast Notifications */}
      <div className="fixed top-4 right-4 z-50 space-y-2 max-w-[calc(100vw-2rem)]">
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
            <span className="text-sm truncate">{toast.message}</span>
            <button
              onClick={() => removeToast(toast.id)}
              className="ml-2 opacity-70 hover:opacity-100 transition-opacity flex-shrink-0"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>

      {/* Settings Modal */}
      <SettingsModal
        isOpen={showSettingsModal}
        onClose={() => setShowSettingsModal(false)}
        currentTheme={currentTheme}
        onThemeChange={handleThemeChange}
        defaultModel={defaultModel}
        onDefaultModelChange={handleDefaultModelChange}
      />

      {/* Mobile Overlay */}
      {isMobile && sidebarOpen && (
        <div 
          className="fixed inset-0 bg-black/60 z-30 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={`
        ${isMobile 
          ? `fixed inset-y-0 left-0 z-40 w-80 transform transition-transform duration-300 ease-out
             ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}`
          : 'w-80 relative'
        }
        border-r border-edge-subtle glass-panel flex flex-col bg-surface-primary
      `}>
        {/* Header */}
        <div className="p-4 md:p-5 border-b border-edge-subtle">
          <div className="flex items-center gap-3">
            {/* Back button on mobile */}
            {isMobile && (
              <button
                onClick={() => setSidebarOpen(false)}
                className="p-2 -ml-2 text-content-tertiary hover:text-content-primary 
                           hover:bg-surface-tertiary rounded-lg transition-colors md:hidden"
              >
                <ChevronLeft className="w-5 h-5" />
              </button>
            )}
            <div className="relative">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-neon-cyan/20 to-violet/20 
                            flex items-center justify-center border border-neon-cyan/30">
                <Terminal className="w-5 h-5 text-neon-cyan" />
              </div>
              <div className={`absolute -top-1 -right-1 w-3 h-3 rounded-full shadow-glow-sm
                ${error ? 'bg-red-500' : 'bg-neon-cyan animate-pulse'}`} />
            </div>
            <div className="flex-1 min-w-0">
              <h1 className="text-lg font-semibold text-content-primary truncate">
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
                         rounded-lg transition-colors flex-shrink-0"
              title="Refresh sessions (⌘+R)"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
            {/* Settings button - Desktop */}
            <div className="hidden md:block">
              <button
                onClick={() => setShowSettingsModal(true)}
                className="flex items-center gap-2 p-2 text-content-tertiary hover:text-content-primary 
                           hover:bg-surface-tertiary rounded-lg transition-colors"
                title="Settings (⌘+,)"
              >
                <Settings className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>

        {/* Error State */}
        {error && !loading && (
          <div className="p-4 m-3 rounded-xl bg-red-500/10 border border-red-500/30">
            <div className="flex items-center gap-2 text-red-400 text-sm">
              <WifiOff className="w-4 h-4" />
              <span>Connection error</span>
            </div>
            <p className="text-xs text-content-tertiary mt-1 break-words">{error}</p>
            <button
              onClick={() => fetchSessions()}
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
          isMobile={isMobile}
        />
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col bg-surface-primary min-w-0">
        {/* Mobile Header */}
        {isMobile && (
          <div className="flex items-center gap-3 p-3 border-b border-edge-subtle glass-panel md:hidden">
            <button
              onClick={() => setSidebarOpen(true)}
              className="p-2 text-content-secondary hover:text-content-primary 
                         hover:bg-surface-tertiary rounded-lg transition-colors"
            >
              <Menu className="w-5 h-5" />
            </button>
            <div className="flex-1 min-w-0">
              {activeSession ? (
                <div>
                  <p className="font-medium text-content-primary truncate">{activeSession.name}</p>
                  <p className="text-xs text-content-tertiary">Tap menu to switch sessions</p>
                </div>
              ) : (
                <p className="text-content-secondary">Select a session</p>
              )}
            </div>
            {/* Settings button - Mobile */}
            <button
              onClick={() => setShowSettingsModal(true)}
              className="p-2 text-content-tertiary hover:text-content-primary 
                         hover:bg-surface-tertiary rounded-lg transition-colors"
              title="Settings"
            >
              <Settings className="w-5 h-5" />
            </button>
          </div>
        )}

        {activeSession ? (
          <ChatInterface 
            session={activeSession} 
            onError={(msg) => addToast('error', msg)} 
            isMobile={isMobile}
          />
        ) : (
          <div className="flex-1 flex items-center justify-center p-4">
            <div className="text-center max-w-md mx-auto px-6">
              {/* Animated icon */}
              <div className="relative mb-8 inline-block">
                <div className="w-20 h-20 md:w-24 md:h-24 rounded-2xl bg-gradient-to-br from-surface-secondary to-surface-tertiary 
                              border border-edge-subtle flex items-center justify-center mx-auto
                              shadow-inner-glow">
                  <MessageSquare className="w-8 h-8 md:w-10 md:h-10 text-content-tertiary" />
                </div>
                {/* Orbiting sparkle */}
                <div className="absolute top-0 right-0 animate-float">
                  <Sparkles className="w-4 h-4 md:w-5 md:h-5 text-neon-cyan opacity-60" />
                </div>
              </div>
              
              <h2 className="text-xl md:text-2xl font-semibold text-content-primary mb-3">
                No Session Selected
              </h2>
              <p className="text-content-secondary leading-relaxed text-sm md:text-base">
                {isMobile 
                  ? 'Tap the menu to select or create a session'
                  : 'Select a session from the sidebar or create a new one to start working'
                }
              </p>
              
              {/* Keyboard shortcuts - hide on mobile */}
              {!isMobile && (
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
              )}

              {/* Mobile CTA */}
              {isMobile && (
                <button
                  onClick={() => setSidebarOpen(true)}
                  className="mt-6 px-6 py-3 bg-neon-cyan text-surface-primary rounded-xl
                             font-semibold hover:shadow-glow transition-all active:scale-95"
                >
                  Open Sessions
                </button>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
