'use client';

import { useState, forwardRef, useImperativeHandle, useRef, useEffect } from 'react';
import { Plus, Clock, CheckCircle, AlertCircle, Archive, Zap, GitBranch, GitPullRequest, CircleDot } from 'lucide-react';

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

interface SessionListProps {
  sessions: Session[];
  activeSession: Session | null;
  loading: boolean;
  onSelectSession: (session: Session) => void;
  onCreateSession: (name: string) => void;
  showNewSessionForm?: boolean;
  onToggleNewSession?: (show: boolean) => void;
  isMobile?: boolean;
}

export interface SessionListRef {
  focusNewSession: () => void;
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

export const SessionList = forwardRef<SessionListRef, SessionListProps>(function SessionList({
  sessions,
  activeSession,
  loading,
  onSelectSession,
  onCreateSession,
  showNewSessionForm = false,
  onToggleNewSession,
  isMobile = false,
}, ref) {
  const [newSessionName, setNewSessionName] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // Expose methods via ref
  useImperativeHandle(ref, () => ({
    focusNewSession: () => {
      onToggleNewSession?.(true);
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }));

  // Focus input when form opens
  useEffect(() => {
    if (showNewSessionForm) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [showNewSessionForm]);

  const handleCreateSession = async () => {
    if (newSessionName.trim() && !isCreating) {
      setIsCreating(true);
      try {
        await onCreateSession(newSessionName.trim());
        setNewSessionName('');
        onToggleNewSession?.(false);
      } finally {
        setIsCreating(false);
      }
    }
  };

  const handleCancel = () => {
    setNewSessionName('');
    onToggleNewSession?.(false);
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
        {showNewSessionForm ? (
          <div className="space-y-3 animate-in">
            <input
              ref={inputRef}
              type="text"
              value={newSessionName}
              onChange={(e) => setNewSessionName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleCreateSession();
                if (e.key === 'Escape') handleCancel();
              }}
              placeholder="session-name..."
              disabled={isCreating}
              className="w-full px-4 py-3 border border-edge-medium rounded-xl 
                         bg-surface-tertiary text-content-primary font-mono text-sm
                         focus:ring-2 focus:ring-neon-cyan/50 focus:border-neon-cyan/50
                         placeholder:text-content-tertiary transition-all outline-none
                         disabled:opacity-50"
            />
            <div className="flex gap-2">
              <button
                onClick={handleCreateSession}
                disabled={!newSessionName.trim() || isCreating}
                className="flex-1 px-4 py-2.5 bg-neon-cyan text-surface-primary rounded-xl
                           hover:shadow-glow transition-all text-sm font-semibold
                           active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isCreating ? 'Creating...' : 'Create'}
              </button>
              <button
                onClick={handleCancel}
                disabled={isCreating}
                className="px-4 py-2.5 text-content-secondary rounded-xl
                           border border-edge-subtle hover:border-edge-medium 
                           hover:bg-surface-tertiary transition-all text-sm
                           disabled:opacity-50"
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <button
            onClick={() => onToggleNewSession?.(true)}
            className="w-full flex items-center justify-center gap-2 px-4 py-3
                       border border-dashed border-edge-medium rounded-xl
                       text-content-secondary hover:text-neon-cyan hover:border-neon-cyan/50
                       hover:bg-neon-cyan/5 transition-all group"
          >
            <Plus className="w-4 h-4 group-hover:rotate-90 transition-transform duration-200" />
            <span className="font-medium">New Session</span>
            {!isMobile && (
              <kbd className="ml-2 px-1.5 py-0.5 bg-surface-tertiary border border-edge-subtle rounded text-[10px] font-mono text-content-tertiary">
                ⌘N
              </kbd>
            )}
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
            <p className="text-content-tertiary text-xs mt-1">
              {isMobile ? 'Tap the button above to create one' : 'Press ⌘+N to create one'}
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {sessions.map((session, index) => {
              const status = getStatusConfig(session.status);
              const isActive = activeSession?.id === session.id;
              const hasGitHub = session.github && (session.github.branch || session.github.issue || session.github.pr);
              
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
                        {/* Quick switch hint */}
                        {index < 9 && (
                          <kbd className="px-1 py-0.5 bg-surface-tertiary/50 border border-edge-subtle/50 
                                        rounded text-[9px] font-mono text-content-tertiary opacity-0 
                                        group-hover:opacity-100 transition-opacity">
                            ⌘{index + 1}
                          </kbd>
                        )}
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
                  
                  {/* GitHub Links */}
                  {hasGitHub && (
                    <div className="flex items-center gap-3 mt-2.5 pl-5">
                      {session.github?.branch && (
                        <span className="flex items-center gap-1 text-xs text-content-tertiary">
                          <GitBranch className="w-3 h-3" />
                          <span className="font-mono truncate max-w-[80px]">{session.github.branch}</span>
                        </span>
                      )}
                      {session.github?.issue && (
                        <a
                          href={session.github.issue.url || '#'}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="flex items-center gap-1 text-xs text-violet hover:text-violet/80 transition-colors"
                        >
                          <CircleDot className="w-3 h-3" />
                          <span>{session.github.issue.number || 'Issue'}</span>
                        </a>
                      )}
                      {session.github?.pr && (
                        <a
                          href={session.github.pr.url || '#'}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="flex items-center gap-1 text-xs text-emerald-400 hover:text-emerald-300 transition-colors"
                        >
                          <GitPullRequest className="w-3 h-3" />
                          <span>{session.github.pr.number || 'PR'}</span>
                        </a>
                      )}
                    </div>
                  )}
                  
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
});
