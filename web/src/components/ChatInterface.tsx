'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { 
  Send, 
  Loader2, 
  Bot, 
  User, 
  AlertTriangle, 
  GitBranch, 
  GitPullRequest, 
  CircleDot, 
  ExternalLink,
  Wrench,
  Brain,
  ListChecks,
  ChevronDown,
  ChevronRight,
  CheckCircle2,
  Clock,
  XCircle,
  Play,
  Copy,
  Check
} from 'lucide-react';
import { VoiceInput } from './VoiceInput';
import { ModelSelector } from './ModelSelector';
import { 
  useSlashCommands, 
  SlashCommandSuggestions, 
  SlashCommandHighlight,
  SlashCommand,
  SLASH_COMMANDS,
  CATEGORY_CONFIG
} from './SlashCommands';

// =============================================================================
// Types
// =============================================================================

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

interface ToolCall {
  id: string;
  title: string;
  kind: string | null;
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
}

interface PlanEntry {
  content: string;
  priority: 'high' | 'medium' | 'low';
  status: 'pending' | 'in_progress' | 'completed';
}

interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  status?: string;
  toolCalls?: ToolCall[];
  thoughts?: string[];
  plan?: PlanEntry[];
}

interface ChatInterfaceProps {
  session: Session;
  onError?: (message: string) => void;
  isMobile?: boolean;
}

// SSE Event types from the backend
type SSEEventType = 
  | 'user_message' 
  | 'start' 
  | 'chunk' 
  | 'thought' 
  | 'tool_call' 
  | 'tool_call_update' 
  | 'plan' 
  | 'mode_change' 
  | 'error' 
  | 'complete';

interface SSEEvent {
  type: SSEEventType;
  data: Record<string, unknown>;
}

// =============================================================================
// Sub-components
// =============================================================================

function CopyButton({ text, className = '' }: { text: string; className?: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  return (
    <button
      onClick={handleCopy}
      className={`p-1.5 rounded-lg transition-all hover:bg-white/10 ${className}`}
      title={copied ? 'Copied!' : 'Copy message'}
    >
      {copied ? (
        <Check className="w-3.5 h-3.5 text-emerald-400" />
      ) : (
        <Copy className="w-3.5 h-3.5 text-content-tertiary hover:text-content-secondary" />
      )}
    </button>
  );
}

function MarkdownContent({ content }: { content: string }) {
  // Clean up excessive newlines that can appear from tool call streaming
  const cleanedContent = content
    .replace(/\n{4,}/g, '\n\n\n') // Reduce 4+ newlines to 3
    .trim();

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        // Style headings
        h1: ({ children }) => <h1 className="text-xl font-bold mt-4 mb-2 text-content-primary">{children}</h1>,
        h2: ({ children }) => <h2 className="text-lg font-semibold mt-3 mb-2 text-content-primary">{children}</h2>,
        h3: ({ children }) => <h3 className="text-base font-semibold mt-2 mb-1 text-content-primary">{children}</h3>,
        // Style paragraphs
        p: ({ children }) => <p className="mb-2 last:mb-0 leading-relaxed">{children}</p>,
        // Style links
        a: ({ href, children }) => (
          <a href={href} target="_blank" rel="noopener noreferrer" 
             className="text-neon-cyan hover:underline">
            {children}
          </a>
        ),
        // Style code blocks
        code: ({ className, children }) => {
          const isInline = !className;
          if (isInline) {
            return <code className="px-1.5 py-0.5 bg-surface-tertiary rounded text-sm font-mono text-neon-cyan">{children}</code>;
          }
          return (
            <code className="block p-3 my-2 bg-surface-tertiary rounded-lg text-sm font-mono overflow-x-auto">
              {children}
            </code>
          );
        },
        pre: ({ children }) => <pre className="my-2">{children}</pre>,
        // Style lists
        ul: ({ children }) => <ul className="list-disc list-inside mb-2 space-y-1">{children}</ul>,
        ol: ({ children }) => <ol className="list-decimal list-inside mb-2 space-y-1">{children}</ol>,
        li: ({ children }) => <li className="text-content-secondary">{children}</li>,
        // Style blockquotes
        blockquote: ({ children }) => (
          <blockquote className="border-l-2 border-neon-cyan/50 pl-3 my-2 text-content-secondary italic">
            {children}
          </blockquote>
        ),
        // Style tables
        table: ({ children }) => (
          <div className="overflow-x-auto my-2">
            <table className="min-w-full border border-edge-subtle rounded-lg overflow-hidden">
              {children}
            </table>
          </div>
        ),
        thead: ({ children }) => <thead className="bg-surface-tertiary">{children}</thead>,
        tbody: ({ children }) => <tbody className="divide-y divide-edge-subtle">{children}</tbody>,
        tr: ({ children }) => <tr className="hover:bg-white/5">{children}</tr>,
        th: ({ children }) => <th className="px-3 py-2 text-left text-xs font-semibold text-content-secondary">{children}</th>,
        td: ({ children }) => <td className="px-3 py-2 text-sm">{children}</td>,
        // Style horizontal rules
        hr: () => <hr className="my-4 border-edge-subtle" />,
        // Style strong/bold
        strong: ({ children }) => <strong className="font-semibold text-content-primary">{children}</strong>,
        // Style emphasis/italic
        em: ({ children }) => <em className="italic">{children}</em>,
      }}
    >
      {cleanedContent}
    </ReactMarkdown>
  );
}

function ToolCallDisplay({ toolCall }: { toolCall: ToolCall }) {
  const [expanded, setExpanded] = useState(false);
  
  const statusIcon = {
    pending: <Clock className="w-3 h-3 text-content-tertiary" />,
    in_progress: <Loader2 className="w-3 h-3 text-neon-cyan animate-spin" />,
    completed: <CheckCircle2 className="w-3 h-3 text-emerald-400" />,
    failed: <XCircle className="w-3 h-3 text-rose-400" />,
  }[toolCall.status];

  const statusColor = {
    pending: 'border-content-tertiary/30',
    in_progress: 'border-neon-cyan/50 bg-neon-cyan/5',
    completed: 'border-emerald-400/30 bg-emerald-400/5',
    failed: 'border-rose-400/30 bg-rose-400/5',
  }[toolCall.status];

  const kindIcon = {
    read: '📖',
    edit: '✏️',
    delete: '🗑️',
    execute: '▶️',
    search: '🔍',
    fetch: '🌐',
    think: '🧠',
    other: '🔧',
  }[toolCall.kind || 'other'] || '🔧';

  return (
    <div 
      className={`mt-2 rounded-lg border ${statusColor} overflow-hidden transition-all`}
    >
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 text-xs text-left hover:bg-white/5 transition-colors"
      >
        {expanded ? (
          <ChevronDown className="w-3 h-3 text-content-tertiary flex-shrink-0" />
        ) : (
          <ChevronRight className="w-3 h-3 text-content-tertiary flex-shrink-0" />
        )}
        <span className="flex-shrink-0">{kindIcon}</span>
        <span className="flex-1 font-medium text-content-secondary truncate">
          {toolCall.title}
        </span>
        {statusIcon}
      </button>
      {expanded && (
        <div className="px-3 pb-2 text-xs text-content-tertiary border-t border-edge-subtle/50">
          <div className="pt-2 space-y-1">
            <div><span className="text-content-tertiary">ID:</span> <span className="font-mono">{toolCall.id}</span></div>
            {toolCall.kind && <div><span className="text-content-tertiary">Kind:</span> {toolCall.kind}</div>}
            <div><span className="text-content-tertiary">Status:</span> {toolCall.status}</div>
          </div>
        </div>
      )}
    </div>
  );
}

function ThoughtDisplay({ thoughts }: { thoughts: string[] }) {
  const [expanded, setExpanded] = useState(false);
  
  if (thoughts.length === 0) return null;
  
  return (
    <div className="mt-2 rounded-lg border border-violet/30 bg-violet/5 overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 text-xs text-left hover:bg-violet/10 transition-colors"
      >
        {expanded ? (
          <ChevronDown className="w-3 h-3 text-violet flex-shrink-0" />
        ) : (
          <ChevronRight className="w-3 h-3 text-violet flex-shrink-0" />
        )}
        <Brain className="w-3 h-3 text-violet flex-shrink-0" />
        <span className="flex-1 font-medium text-violet">
          Agent Thoughts ({thoughts.length})
        </span>
      </button>
      {expanded && (
        <div className="px-3 pb-2 text-xs text-content-secondary border-t border-violet/20">
          <div className="pt-2 space-y-2">
            {thoughts.map((thought, i) => (
              <p key={i} className="italic text-violet/80">{thought}</p>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function PlanDisplay({ plan }: { plan: PlanEntry[] }) {
  const [expanded, setExpanded] = useState(true);
  
  if (plan.length === 0) return null;

  const priorityColor = {
    high: 'text-rose-400',
    medium: 'text-amber',
    low: 'text-content-tertiary',
  };

  const statusIcon = {
    pending: <Clock className="w-3 h-3 text-content-tertiary" />,
    in_progress: <Play className="w-3 h-3 text-neon-cyan" />,
    completed: <CheckCircle2 className="w-3 h-3 text-emerald-400" />,
  };
  
  return (
    <div className="mt-2 rounded-lg border border-amber/30 bg-amber/5 overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 text-xs text-left hover:bg-amber/10 transition-colors"
      >
        {expanded ? (
          <ChevronDown className="w-3 h-3 text-amber flex-shrink-0" />
        ) : (
          <ChevronRight className="w-3 h-3 text-amber flex-shrink-0" />
        )}
        <ListChecks className="w-3 h-3 text-amber flex-shrink-0" />
        <span className="flex-1 font-medium text-amber">
          Plan ({plan.filter(e => e.status === 'completed').length}/{plan.length})
        </span>
      </button>
      {expanded && (
        <div className="px-3 pb-2 text-xs border-t border-amber/20">
          <ul className="pt-2 space-y-1.5">
            {plan.map((entry, i) => (
              <li key={i} className="flex items-start gap-2">
                {statusIcon[entry.status]}
                <span className={`flex-1 ${entry.status === 'completed' ? 'line-through text-content-tertiary' : 'text-content-secondary'}`}>
                  {entry.content}
                </span>
                <span className={`text-[10px] ${priorityColor[entry.priority]}`}>
                  {entry.priority}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

// =============================================================================
// SSE Parser
// =============================================================================

function parseSSEEvents(chunk: string): SSEEvent[] {
  const events: SSEEvent[] = [];
  const lines = chunk.split('\n');
  
  let currentEvent: string | null = null;
  let currentData: string | null = null;
  
  for (const line of lines) {
    if (line.startsWith('event: ')) {
      currentEvent = line.slice(7).trim() as SSEEventType;
    } else if (line.startsWith('data: ')) {
      currentData = line.slice(6);
    } else if (line === '' && currentEvent && currentData) {
      // Empty line = end of event
      try {
        const data = JSON.parse(currentData);
        events.push({ type: currentEvent as SSEEventType, data });
      } catch {
        console.warn('Failed to parse SSE data:', currentData);
      }
      currentEvent = null;
      currentData = null;
    }
  }
  
  return events;
}

// =============================================================================
// Main Component
// =============================================================================

export function ChatInterface({ session, onError, isMobile = false }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Slash command suggestions
  const slashCommands = useSlashCommands(input);

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
        toolCalls: [],
        thoughts: [],
        plan: [],
      };

      setMessages((prev) => [...prev, assistantMessage]);

      let buffer = '';

      while (reader) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        
        // Process complete events (ending with double newline)
        const events = parseSSEEvents(buffer);
        
        // Keep incomplete data in buffer
        const lastDoubleNewline = buffer.lastIndexOf('\n\n');
        if (lastDoubleNewline !== -1) {
          buffer = buffer.slice(lastDoubleNewline + 2);
        }

        for (const event of events) {
          switch (event.type) {
            case 'user_message':
              // Update user message ID if provided
              if (event.data.id) {
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === userMessage.id ? { ...m, id: event.data.id as string } : m
                  )
                );
              }
              break;

            case 'start':
              // Update assistant message ID
              if (event.data.id) {
                assistantMessage = { ...assistantMessage, id: event.data.id as string };
                setMessages((prev) =>
                  prev.map((m) =>
                    m.status === 'streaming' && m.role === 'assistant'
                      ? { ...m, id: event.data.id as string }
                      : m
                  )
                );
              }
              break;

            case 'chunk':
              // Append content chunk
              if (event.data.content) {
                assistantMessage = {
                  ...assistantMessage,
                  content: assistantMessage.content + (event.data.content as string),
                };
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantMessage.id ? assistantMessage : m
                  )
                );
              }
              break;

            case 'thought':
              // Add agent thought
              if (event.data.content) {
                assistantMessage = {
                  ...assistantMessage,
                  thoughts: [...(assistantMessage.thoughts || []), event.data.content as string],
                };
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantMessage.id ? assistantMessage : m
                  )
                );
              }
              break;

            case 'tool_call':
              // Add new tool call
              const toolCall: ToolCall = {
                id: event.data.id as string,
                title: event.data.title as string,
                kind: event.data.kind as string | null,
                status: (event.data.status as ToolCall['status']) || 'pending',
              };
              assistantMessage = {
                ...assistantMessage,
                toolCalls: [...(assistantMessage.toolCalls || []), toolCall],
              };
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantMessage.id ? assistantMessage : m
                )
              );
              break;

            case 'tool_call_update':
              // Update existing tool call
              if (event.data.id) {
                assistantMessage = {
                  ...assistantMessage,
                  toolCalls: (assistantMessage.toolCalls || []).map((tc) =>
                    tc.id === event.data.id
                      ? {
                          ...tc,
                          status: (event.data.status as ToolCall['status']) || tc.status,
                          title: (event.data.title as string) || tc.title,
                        }
                      : tc
                  ),
                };
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantMessage.id ? assistantMessage : m
                  )
                );
              }
              break;

            case 'plan':
              // Update plan entries
              if (event.data.entries) {
                const entries = event.data.entries as Array<{
                  content: string;
                  priority: 'high' | 'medium' | 'low';
                  status: 'pending' | 'in_progress' | 'completed';
                }>;
                assistantMessage = {
                  ...assistantMessage,
                  plan: entries,
                };
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantMessage.id ? assistantMessage : m
                  )
                );
              }
              break;

            case 'error':
              // Handle error
              const errorMsg = event.data.error as string || 'Unknown error';
              onError?.(errorMsg);
              assistantMessage = {
                ...assistantMessage,
                content: assistantMessage.content + `\n\n⚠️ Error: ${errorMsg}`,
              };
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantMessage.id ? assistantMessage : m
                )
              );
              break;

            case 'complete':
              // Mark as complete
              assistantMessage = {
                ...assistantMessage,
                status: 'complete',
                content: (event.data.content as string) || assistantMessage.content,
              };
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantMessage.id ? assistantMessage : m
                )
              );
              break;

            case 'mode_change':
              // Could show mode change notification
              console.log('Mode changed to:', event.data.modeId);
              break;
          }
        }
      }

      // Ensure message is marked complete
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantMessage.id ? { ...m, status: 'complete' } : m
        )
      );
    } catch (error) {
      console.error('Failed to send message:', error);
      const errorMsg = 'Failed to get response. Please try again.';
      onError?.(errorMsg);
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

  // Handle selecting a slash command from suggestions
  const handleSlashCommandSelect = useCallback((command: SlashCommand) => {
    // Replace input with command (add space if command has args)
    const newInput = command.args ? `${command.command} ` : command.command;
    setInput(newInput);
    inputRef.current?.focus();
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    // Handle slash command navigation
    if (slashCommands.isActive) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        slashCommands.selectNext();
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        slashCommands.selectPrev();
        return;
      }
      if (e.key === 'Tab' || (e.key === 'Enter' && !e.shiftKey)) {
        const selected = slashCommands.getSelected();
        if (selected) {
          e.preventDefault();
          handleSlashCommandSelect(selected);
          return;
        }
      }
      if (e.key === 'Escape') {
        e.preventDefault();
        // Clear slash command by removing the /
        if (input.startsWith('/')) {
          setInput('');
        }
        return;
      }
    }
    
    // Normal enter to send
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
                    {/* Tool Calls - render ABOVE text so response stays visible at bottom */}
                    {message.toolCalls && message.toolCalls.length > 0 && (
                      <div className="mb-3 pb-3 border-b border-edge-subtle/50">
                        <div className="flex items-center gap-1.5 text-xs text-content-tertiary mb-2">
                          <Wrench className="w-3 h-3" />
                          <span>Tool Calls ({message.toolCalls.length})</span>
                        </div>
                        {message.toolCalls.map((tc) => (
                          <ToolCallDisplay key={tc.id} toolCall={tc} />
                        ))}
                      </div>
                    )}
                    
                    {/* Thoughts - render above main content */}
                    {message.thoughts && message.thoughts.length > 0 && (
                      <div className="mb-3">
                        <ThoughtDisplay thoughts={message.thoughts} />
                      </div>
                    )}
                    
                    {/* Plan - render above main content */}
                    {message.plan && message.plan.length > 0 && (
                      <div className="mb-3">
                        <PlanDisplay plan={message.plan} />
                      </div>
                    )}
                    
                    {/* Main text content - renders at bottom so it stays visible */}
                    <div className="prose-sm max-w-none">
                      <MarkdownContent content={message.content} />
                    </div>
                    {message.status === 'streaming' && (
                      <span className="inline-block w-2 h-4 md:h-5 bg-neon-cyan ml-1 typing-cursor" />
                    )}
                  </div>
                  <div className={`mt-1 md:mt-1.5 flex items-center gap-2 text-[10px] md:text-xs text-content-tertiary ${message.role === 'user' ? 'justify-end' : ''}`}>
                    <span>{formatTime(message.timestamp)}</span>
                    <CopyButton text={message.content} />
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
        {/* Model selector row */}
        <div className="flex items-center justify-between mb-2 max-w-4xl mx-auto">
          <ModelSelector sessionId={session.id} />
          {streaming && (
            <span className="text-xs text-neon-cyan flex items-center gap-1.5">
              <Loader2 className="w-3 h-3 animate-spin" />
              Generating...
            </span>
          )}
        </div>
        
        <div className="flex items-end gap-2 md:gap-3 max-w-4xl mx-auto">
          <div className="flex-1 relative min-w-0">
            {/* Slash Command Suggestions */}
            {slashCommands.isActive && (
              <SlashCommandSuggestions
                suggestions={slashCommands.suggestions}
                selectedIndex={slashCommands.selectedIndex}
                onSelect={handleSlashCommandSelect}
                onHover={slashCommands.setSelectedIndex}
              />
            )}
            
            {/* Input with slash command highlight overlay */}
            <div className="relative">
              {/* Highlighted overlay - shows colored slash commands */}
              {input.startsWith('/') && (
                <div 
                  className="absolute inset-0 px-3 py-3 md:px-5 md:py-4 pointer-events-none 
                             text-sm md:text-base whitespace-pre-wrap break-words overflow-hidden"
                  aria-hidden="true"
                >
                  <SlashCommandHighlight value={input} />
                </div>
              )}
              
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Type a message or / for commands..."
                rows={1}
                className={`w-full px-3 py-3 md:px-5 md:py-4 border border-edge-medium rounded-xl md:rounded-2xl 
                           bg-surface-secondary text-sm md:text-base
                           focus:ring-2 focus:ring-neon-cyan/30 focus:border-neon-cyan/50
                           placeholder:text-content-tertiary resize-none transition-all
                           outline-none
                           ${input.startsWith('/') ? 'text-transparent caret-content-primary' : 'text-content-primary'}`}
                style={{ minHeight: isMobile ? '44px' : '56px', maxHeight: '150px' }}
              />
            </div>
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
                /
              </kbd>
              commands
            </span>
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
