'use client';

import { useState } from 'react';
import { Plus, Clock, CheckCircle, AlertCircle, Archive, Zap } from 'lucide-react';

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

const statusConfig: Record<string, { icon: React.ReactNode; color: string; label: string }> = {
  active: {
    icon: <Zap className="w-3.5 h-3.5" />,
    color: 'text-neon-cyan',
    label: 'Active'
  },
  completed: {
    icon: <CheckCircle className="w-3.5 h-3.5" />,
    color: 'text-emerald-400',
    label: 'Complete'
  },
  blocked: {
    icon: <AlertCircle className="w-3.5 h-3.5" />,
    color: 'text-amber',
    label: 'Blocked'
  },
  archived: {
    icon: <Archive className="w-3.5 h-3.5" />,
    color: 'text-content-tertiary',
    label: 'Archived'
  },
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

  const getStatusConfig = (status: string) => {
    return statusConfig[status] || statusConfig.active;
  };

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* New Session Button */}
      <div className="p-4">
        {showNewSession ? (
          <div className="space-y-3 animate-in">
            <input
              type="text"
              value={newSessionName}
              onChange={(e) => setNewSessionName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleCreateSession()}
              placeholder="session-name..."
              className="w-full px-4 py-3 border border-edge-medium rounded-xl 
                         bg-surface-tertiary text-content-primary font-mono text-sm
                         focus:ring-2 focus:ring-neon-cyan/50 focus:border-neon-cyan/50
                         placeholder:text-content-tertiary transition-all outline-none"
              autoFocus
            />
            <div className="flex gap-2">
              <button
                onClick={handleCreateSession}
                className="flex-1 px-4 py-2.5 bg-neon-cyan text-surface-primary rounded-xl
                           hover:shadow-glow transition-all text-sm font-semibold
                           active:scale-[0.98]"
              >
                Create
              </button>
              <button
                onClick={() => setShowNewSession(false)}
                className="px-4 py-2.5 text-content-secondary rounded-xl
                           border border-edge-subtle hover:border-edge-medium 
                           hover:bg-surface-tertiary transition-all text-sm"
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <button
            onClick={() => setShowNewSession(true)}
            className="w-full flex items-center justify-center gap-2 px-4 py-3
                       border border-dashed border-edge-medium rounded-xl
                       text-content-secondary hover:text-neon-cyan hover:border-neon-cyan/50
                       hover:bg-neon-cyan/5 transition-all group"
          >
            <Plus className="w-4 h-4 group-hover:rotate-90 transition-transform duration-200" />
            <span className="font-medium">New Session</span>
          </button>
        )}
      </div>

      {/* Sessions */}
      <div className="flex-1 overflow-y-auto px-3 pb-4">
        {loading ? (
          <div className="space-y-3 p-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="p-4 rounded-xl bg-surface-tertiary shimmer h-20" />
            ))}
          </div>
        ) : sessions.length === 0 ? (
          <div className="text-center py-12 px-4">
            <div className="w-16 h-16 rounded-2xl bg-surface-tertiary border border-edge-subtle 
                          flex items-center justify-center mx-auto mb-4">
              <Clock className="w-7 h-7 text-content-tertiary" />
            </div>
            <p className="text-content-secondary text-sm">No sessions yet</p>
            <p className="text-content-tertiary text-xs mt-1">Create one to get started</p>
          </div>
        ) : (
          <div className="space-y-2">
            {sessions.map((session, index) => {
              const status = getStatusConfig(session.status);
              const isActive = activeSession?.id === session.id;
              
              return (
                <button
                  key={session.id}
                  onClick={() => onSelectSession(session)}
                  className={`w-full text-left p-4 rounded-xl transition-all hover-lift
                    ${isActive
                      ? 'bg-surface-elevated border border-neon-cyan/30 shadow-glow-sm'
                      : 'bg-surface-secondary/50 border border-transparent hover:bg-surface-tertiary hover:border-edge-subtle'
                    }`}
                  style={{ animationDelay: `${index * 50}ms` }}
                >
                  {/* Header */}
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className={`${status.color}`}>
                          {status.icon}
                        </span>
                        <span className={`font-medium truncate ${isActive ? 'text-content-primary' : 'text-content-secondary'}`}>
                          {session.name}
                        </span>
                      </div>
                      
                      {session.active_work && (
                        <p className="text-xs text-content-tertiary mt-1.5 truncate pl-5">
                          {session.active_work}
                        </p>
                      )}
                    </div>
                    
                    {isActive && (
                      <div className="w-2 h-2 rounded-full bg-neon-cyan animate-pulse" />
                    )}
                  </div>
                  
                  {/* Footer */}
                  <div className="flex items-center justify-between mt-3 pl-5">
                    <span className="text-xs text-content-tertiary font-mono">
                      cycle #{session.compaction_cycle}
                    </span>
                    <span className="text-xs text-content-tertiary">
                      {formatDate(session.updated_at)}
                    </span>
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
