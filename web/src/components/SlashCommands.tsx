'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { 
  Terminal, 
  FolderOpen, 
  List, 
  FileText, 
  Cpu, 
  Zap,
  GitBranch,
  GitPullRequest,
  MessageSquare,
  Trash2,
  RotateCcw,
  Settings,
  HelpCircle,
  Search,
  Code,
  Package
} from 'lucide-react';

// =============================================================================
// Types
// =============================================================================

export interface SlashCommand {
  command: string;
  description: string;
  category: 'context-harness' | 'opencode' | 'general';
  args?: string;
  icon: React.ReactNode;
}

// =============================================================================
// Slash Commands Registry
// =============================================================================

const SLASH_COMMANDS: SlashCommand[] = [
  // ContextHarness commands
  {
    command: '/ctx',
    description: 'Switch to or create a ContextHarness session',
    category: 'context-harness',
    args: '<session-name>',
    icon: <FolderOpen className="w-4 h-4" />,
  },
  {
    command: '/contexts',
    description: 'List all available ContextHarness sessions',
    category: 'context-harness',
    icon: <List className="w-4 h-4" />,
  },
  {
    command: '/baseline',
    description: 'Generate PROJECT-CONTEXT.md through analysis',
    category: 'context-harness',
    args: '[--flags]',
    icon: <FileText className="w-4 h-4" />,
  },
  {
    command: '/compact',
    description: 'Manually trigger context compaction',
    category: 'context-harness',
    icon: <Package className="w-4 h-4" />,
  },
  
  // OpenCode commands
  {
    command: '/model',
    description: 'Switch to a different AI model',
    category: 'opencode',
    args: '<provider/model>',
    icon: <Cpu className="w-4 h-4" />,
  },
  {
    command: '/agent',
    description: 'Switch to a different agent mode',
    category: 'opencode',
    args: '<agent-name>',
    icon: <Zap className="w-4 h-4" />,
  },
  {
    command: '/issue',
    description: 'Create or link a GitHub issue',
    category: 'opencode',
    args: '[number|url]',
    icon: <GitBranch className="w-4 h-4" />,
  },
  {
    command: '/pr',
    description: 'Create or view a pull request',
    category: 'opencode',
    args: '[number]',
    icon: <GitPullRequest className="w-4 h-4" />,
  },
  {
    command: '/clear',
    description: 'Clear the current conversation',
    category: 'opencode',
    icon: <Trash2 className="w-4 h-4" />,
  },
  {
    command: '/retry',
    description: 'Retry the last message',
    category: 'opencode',
    icon: <RotateCcw className="w-4 h-4" />,
  },
  {
    command: '/config',
    description: 'View or modify configuration',
    category: 'opencode',
    args: '[key] [value]',
    icon: <Settings className="w-4 h-4" />,
  },
  {
    command: '/help',
    description: 'Show available commands',
    category: 'opencode',
    icon: <HelpCircle className="w-4 h-4" />,
  },
  {
    command: '/search',
    description: 'Search the codebase',
    category: 'opencode',
    args: '<query>',
    icon: <Search className="w-4 h-4" />,
  },
  {
    command: '/diff',
    description: 'Show git diff',
    category: 'opencode',
    args: '[file]',
    icon: <Code className="w-4 h-4" />,
  },
  {
    command: '/status',
    description: 'Show git status',
    category: 'opencode',
    icon: <GitBranch className="w-4 h-4" />,
  },
  {
    command: '/commit',
    description: 'Create a git commit',
    category: 'opencode',
    args: '[message]',
    icon: <MessageSquare className="w-4 h-4" />,
  },
];

// Category colors and labels
const CATEGORY_CONFIG = {
  'context-harness': {
    label: 'ContextHarness',
    color: 'text-neon-cyan',
    bgColor: 'bg-neon-cyan/10',
    borderColor: 'border-neon-cyan/30',
  },
  'opencode': {
    label: 'OpenCode',
    color: 'text-violet',
    bgColor: 'bg-violet/10',
    borderColor: 'border-violet/30',
  },
  'general': {
    label: 'General',
    color: 'text-content-secondary',
    bgColor: 'bg-surface-tertiary',
    borderColor: 'border-edge-subtle',
  },
};

// =============================================================================
// Hook: useSlashCommands
// =============================================================================

export function useSlashCommands(input: string) {
  const [suggestions, setSuggestions] = useState<SlashCommand[]>([]);
  const [isActive, setIsActive] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  
  useEffect(() => {
    // Check if input starts with /
    if (input.startsWith('/')) {
      const query = input.toLowerCase();
      
      // Filter commands that match
      const matches = SLASH_COMMANDS.filter(cmd => 
        cmd.command.toLowerCase().startsWith(query) ||
        cmd.description.toLowerCase().includes(query.slice(1))
      );
      
      setSuggestions(matches);
      setIsActive(matches.length > 0);
      setSelectedIndex(0);
    } else {
      setSuggestions([]);
      setIsActive(false);
    }
  }, [input]);
  
  const selectNext = useCallback(() => {
    setSelectedIndex(i => (i + 1) % suggestions.length);
  }, [suggestions.length]);
  
  const selectPrev = useCallback(() => {
    setSelectedIndex(i => (i - 1 + suggestions.length) % suggestions.length);
  }, [suggestions.length]);
  
  const getSelected = useCallback(() => {
    return suggestions[selectedIndex];
  }, [suggestions, selectedIndex]);
  
  return {
    suggestions,
    isActive,
    selectedIndex,
    setSelectedIndex,
    selectNext,
    selectPrev,
    getSelected,
  };
}

// =============================================================================
// Component: SlashCommandSuggestions
// =============================================================================

interface SlashCommandSuggestionsProps {
  suggestions: SlashCommand[];
  selectedIndex: number;
  onSelect: (command: SlashCommand) => void;
  onHover: (index: number) => void;
}

export function SlashCommandSuggestions({
  suggestions,
  selectedIndex,
  onSelect,
  onHover,
}: SlashCommandSuggestionsProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  
  // Scroll selected item into view
  useEffect(() => {
    if (containerRef.current) {
      const selectedElement = containerRef.current.querySelector(
        `[data-index="${selectedIndex}"]`
      ) as HTMLElement;
      if (selectedElement) {
        selectedElement.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      }
    }
  }, [selectedIndex]);
  
  if (suggestions.length === 0) return null;
  
  // Group by category
  const grouped = suggestions.reduce((acc, cmd) => {
    if (!acc[cmd.category]) acc[cmd.category] = [];
    acc[cmd.category].push(cmd);
    return acc;
  }, {} as Record<string, SlashCommand[]>);
  
  return (
    <div 
      ref={containerRef}
      className="absolute bottom-full left-0 right-0 mb-2 max-h-[300px] overflow-y-auto
                 bg-surface-elevated border border-edge-subtle rounded-xl shadow-2xl z-50"
    >
      <div className="p-2">
        <div className="flex items-center gap-2 px-2 py-1 text-xs text-content-tertiary mb-1">
          <Terminal className="w-3 h-3" />
          <span>Slash Commands</span>
          <span className="ml-auto text-[10px]">↑↓ navigate • Enter select • Esc close</span>
        </div>
        
        {Object.entries(grouped).map(([category, commands]) => {
          const config = CATEGORY_CONFIG[category as keyof typeof CATEGORY_CONFIG];
          
          return (
            <div key={category} className="mb-2 last:mb-0">
              {/* Category header */}
              <div className={`px-2 py-1 text-[10px] font-semibold ${config.color} uppercase tracking-wider`}>
                {config.label}
              </div>
              
              {/* Commands */}
              {commands.map((cmd) => {
                const index = suggestions.indexOf(cmd);
                const isSelected = index === selectedIndex;
                
                return (
                  <button
                    key={cmd.command}
                    data-index={index}
                    onClick={() => onSelect(cmd)}
                    onMouseEnter={() => onHover(index)}
                    className={`
                      w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left
                      transition-colors cursor-pointer
                      ${isSelected 
                        ? `${config.bgColor} ${config.borderColor} border` 
                        : 'hover:bg-surface-tertiary border border-transparent'
                      }
                    `}
                  >
                    <span className={`flex-shrink-0 ${config.color}`}>
                      {cmd.icon}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className={`font-mono font-medium ${isSelected ? config.color : 'text-content-primary'}`}>
                          {cmd.command}
                        </span>
                        {cmd.args && (
                          <span className="text-xs text-content-tertiary font-mono">
                            {cmd.args}
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-content-tertiary truncate">
                        {cmd.description}
                      </p>
                    </div>
                  </button>
                );
              })}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// =============================================================================
// Component: SlashCommandHighlight (for showing slash command highlighting)
// =============================================================================

interface SlashCommandHighlightProps {
  value: string;
  className?: string;
}

export function SlashCommandHighlight({ value, className = '' }: SlashCommandHighlightProps) {
  // Parse and highlight slash commands in the input
  const parts: React.ReactNode[] = [];
  
  // Check if starts with a slash command
  const commandMatch = value.match(/^(\/\w+)(\s.*)?$/);
  
  if (commandMatch) {
    const [, command, rest] = commandMatch;
    const knownCommand = SLASH_COMMANDS.find(c => c.command === command);
    const config = knownCommand 
      ? CATEGORY_CONFIG[knownCommand.category]
      : CATEGORY_CONFIG.general;
    
    parts.push(
      <span key="cmd" className={`font-mono font-semibold ${config.color}`}>
        {command}
      </span>
    );
    
    if (rest) {
      parts.push(
        <span key="rest" className="text-content-primary">
          {rest}
        </span>
      );
    }
  } else {
    parts.push(<span key="text">{value}</span>);
  }
  
  return (
    <div className={`pointer-events-none whitespace-pre-wrap break-words ${className}`}>
      {parts}
    </div>
  );
}

// =============================================================================
// Export all commands for reference
// =============================================================================

export { SLASH_COMMANDS, CATEGORY_CONFIG };
