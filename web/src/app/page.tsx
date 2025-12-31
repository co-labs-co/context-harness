'use client';

import { useState, useEffect } from 'react';
import { SessionList } from '@/components/SessionList';
import { ChatInterface } from '@/components/ChatInterface';
import { MessageSquare, Sparkles, Terminal } from 'lucide-react';

interface Session {
  id: string;
  name: string;
  status: string;
  created_at: string;
  updated_at: string;
  compaction_cycle: number;
  active_work: string | null;
}

export default function Home() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSession, setActiveSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchSessions();
  }, []);

  const fetchSessions = async () => {
    try {
      const response = await fetch('/api/sessions');
      if (response.ok) {
        const data = await response.json();
        setSessions(data.sessions);
        // Auto-select first session if available
        if (data.sessions.length > 0 && !activeSession) {
          setActiveSession(data.sessions[0]);
        }
      }
    } catch (error) {
      console.error('Failed to fetch sessions:', error);
    } finally {
      setLoading(false);
    }
  };

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
      if (response.ok) {
        const newSession = await response.json();
        setSessions(prev => [newSession, ...prev]);
        setActiveSession(newSession);
      }
    } catch (error) {
      console.error('Failed to create session:', error);
    }
  };

  return (
    <div className="flex h-screen bg-surface-primary">
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
              <div className="absolute -top-1 -right-1 w-3 h-3 bg-neon-cyan rounded-full 
                            animate-pulse shadow-glow-sm" />
            </div>
            <div>
              <h1 className="text-lg font-semibold text-content-primary flex items-center gap-2">
                ContextHarness
              </h1>
              <p className="text-xs text-content-tertiary font-mono">
                session://manager
              </p>
            </div>
          </div>
        </div>

        {/* Sessions List */}
        <SessionList
          sessions={sessions}
          activeSession={activeSession}
          loading={loading}
          onSelectSession={handleSelectSession}
          onCreateSession={handleCreateSession}
        />
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col bg-surface-primary">
        {activeSession ? (
          <ChatInterface session={activeSession} />
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
              
              {/* Keyboard shortcut hint */}
              <div className="mt-8 flex items-center justify-center gap-2 text-content-tertiary text-sm">
                <kbd className="px-2 py-1 bg-surface-tertiary border border-edge-subtle rounded text-xs font-mono">
                  ⌘
                </kbd>
                <span>+</span>
                <kbd className="px-2 py-1 bg-surface-tertiary border border-edge-subtle rounded text-xs font-mono">
                  N
                </kbd>
                <span className="ml-2">New session</span>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
