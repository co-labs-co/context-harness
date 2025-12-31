'use client';

import { useState } from 'react';
import { Plus, Clock, CheckCircle, AlertCircle, Archive } from 'lucide-react';

interface Session {
  id: string;
  name: string;
  status: string;
  created_at: string;
  updated_at: string;
  compaction_cycle: number;
  active_work: string | null;
}

interface SessionListProps {
  sessions: Session[];
  activeSession: Session | null;
  loading: boolean;
  onSelectSession: (session: Session) => void;
  onCreateSession: (name: string) => void;
}

const statusIcons: Record<string, React.ReactNode> = {
  active: <Clock className="w-4 h-4 text-blue-500" />,
  completed: <CheckCircle className="w-4 h-4 text-green-500" />,
  blocked: <AlertCircle className="w-4 h-4 text-red-500" />,
  archived: <Archive className="w-4 h-4 text-slate-400" />,
};

export function SessionList({
  sessions,
  activeSession,
  loading,
  onSelectSession,
  onCreateSession,
}: SessionListProps) {
  const [showNewSession, setShowNewSession] = useState(false);
  const [newSessionName, setNewSessionName] = useState('');

  const handleCreateSession = () => {
    if (newSessionName.trim()) {
      onCreateSession(newSessionName.trim());
      setNewSessionName('');
      setShowNewSession(false);
    }
  };

  const formatDate = (dateStr: string) => {
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return dateStr;
    }
  };

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* New Session Button */}
      <div className="p-3">
        {showNewSession ? (
          <div className="space-y-2">
            <input
              type="text"
              value={newSessionName}
              onChange={(e) => setNewSessionName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleCreateSession()}
              placeholder="Session name..."
              className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg 
                         bg-white dark:bg-slate-700 text-slate-900 dark:text-white
                         focus:ring-2 focus:ring-primary-500 focus:border-transparent
                         placeholder:text-slate-400"
              autoFocus
            />
            <div className="flex gap-2">
              <button
                onClick={handleCreateSession}
                className="flex-1 px-3 py-1.5 bg-primary-500 text-white rounded-lg
                           hover:bg-primary-600 transition-colors text-sm font-medium"
              >
                Create
              </button>
              <button
                onClick={() => setShowNewSession(false)}
                className="px-3 py-1.5 text-slate-600 dark:text-slate-400 rounded-lg
                           hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors text-sm"
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <button
            onClick={() => setShowNewSession(true)}
            className="w-full flex items-center justify-center gap-2 px-4 py-2
                       border-2 border-dashed border-slate-300 dark:border-slate-600
                       rounded-lg text-slate-600 dark:text-slate-400
                       hover:border-primary-500 hover:text-primary-500
                       transition-colors"
          >
            <Plus className="w-4 h-4" />
            New Session
          </button>
        )}
      </div>

      {/* Sessions */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="p-4 text-center text-slate-500">
            Loading sessions...
          </div>
        ) : sessions.length === 0 ? (
          <div className="p-4 text-center text-slate-500">
            No sessions yet. Create one to get started!
          </div>
        ) : (
          <div className="space-y-1 p-2">
            {sessions.map((session) => (
              <button
                key={session.id}
                onClick={() => onSelectSession(session)}
                className={`w-full text-left p-3 rounded-lg transition-colors ${
                  activeSession?.id === session.id
                    ? 'bg-primary-50 dark:bg-primary-900/20 border border-primary-200 dark:border-primary-800'
                    : 'hover:bg-slate-100 dark:hover:bg-slate-700/50'
                }`}
              >
                <div className="flex items-center gap-2">
                  {statusIcons[session.status] || statusIcons.active}
                  <span className="font-medium text-slate-900 dark:text-white truncate">
                    {session.name}
                  </span>
                </div>
                {session.active_work && (
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 truncate pl-6">
                    {session.active_work}
                  </p>
                )}
                <div className="flex items-center justify-between mt-2 pl-6">
                  <span className="text-xs text-slate-400">
                    Cycle #{session.compaction_cycle}
                  </span>
                  <span className="text-xs text-slate-400">
                    {formatDate(session.updated_at)}
                  </span>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
