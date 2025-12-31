'use client';

import { useState, useEffect } from 'react';
import { SessionList } from '@/components/SessionList';
import { ChatInterface } from '@/components/ChatInterface';
import { MessageSquare, FolderOpen } from 'lucide-react';

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
    <div className="flex h-screen">
      {/* Sidebar */}
      <aside className="w-80 border-r border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 flex flex-col">
        {/* Header */}
        <div className="p-4 border-b border-slate-200 dark:border-slate-700">
          <h1 className="text-xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <FolderOpen className="w-6 h-6 text-primary-500" />
            ContextHarness
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            Session Manager
          </p>
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
      <main className="flex-1 flex flex-col">
        {activeSession ? (
          <ChatInterface session={activeSession} />
        ) : (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <MessageSquare className="w-16 h-16 text-slate-300 dark:text-slate-600 mx-auto mb-4" />
              <h2 className="text-xl font-semibold text-slate-600 dark:text-slate-400">
                No Session Selected
              </h2>
              <p className="text-slate-500 dark:text-slate-500 mt-2">
                Select a session from the sidebar or create a new one
              </p>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
