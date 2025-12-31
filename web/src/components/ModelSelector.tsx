'use client';

import { useState, useEffect, useRef } from 'react';
import { ChevronDown, Cpu, Check, Loader2 } from 'lucide-react';

// =============================================================================
// Types
// =============================================================================

interface ModelInfo {
  id: string;
  provider: string;
  name: string;
  display_name: string;
}

interface ModelSelectorProps {
  sessionId: string;
  onModelChange?: (modelId: string) => void;
  compact?: boolean;
}

// Provider colors for visual distinction
const PROVIDER_COLORS: Record<string, string> = {
  'github-copilot': 'text-violet',
  'google': 'text-blue-400',
  'openrouter': 'text-emerald-400',
  'opencode': 'text-neon-cyan',
};

// Provider display names
const PROVIDER_NAMES: Record<string, string> = {
  'github-copilot': 'GitHub Copilot',
  'google': 'Google',
  'openrouter': 'OpenRouter',
  'opencode': 'OpenCode',
};

// =============================================================================
// Component
// =============================================================================

export function ModelSelector({ sessionId, onModelChange, compact = false }: ModelSelectorProps) {
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [currentModel, setCurrentModel] = useState<string>('');
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [changing, setChanging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Fetch available models on mount
  useEffect(() => {
    fetchModels();
    fetchCurrentModel();
  }, [sessionId]);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const fetchModels = async () => {
    try {
      const response = await fetch('/api/chat/models');
      if (response.ok) {
        const data = await response.json();
        setModels(data.models || []);
        if (data.current_model && !currentModel) {
          setCurrentModel(data.current_model);
        }
      } else {
        setError('Failed to load models');
      }
    } catch (err) {
      console.error('Failed to fetch models:', err);
      setError('Failed to load models');
    } finally {
      setLoading(false);
    }
  };

  const fetchCurrentModel = async () => {
    try {
      const response = await fetch(`/api/chat/${sessionId}/model`);
      if (response.ok) {
        const data = await response.json();
        if (data.model_id) {
          setCurrentModel(data.model_id);
        }
      }
    } catch (err) {
      console.error('Failed to fetch current model:', err);
    }
  };

  const selectModel = async (modelId: string) => {
    if (modelId === currentModel) {
      setIsOpen(false);
      return;
    }

    setChanging(true);
    setIsOpen(false);

    try {
      const response = await fetch(`/api/chat/${sessionId}/model`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model_id: modelId }),
      });

      if (response.ok) {
        const data = await response.json();
        if (data.success) {
          setCurrentModel(modelId);
          onModelChange?.(modelId);
        } else {
          setError(data.message || 'Failed to set model');
        }
      } else {
        setError('Failed to set model');
      }
    } catch (err) {
      console.error('Failed to set model:', err);
      setError('Failed to set model');
    } finally {
      setChanging(false);
    }
  };

  // Group models by provider
  const modelsByProvider = models.reduce((acc, model) => {
    if (!acc[model.provider]) {
      acc[model.provider] = [];
    }
    acc[model.provider].push(model);
    return acc;
  }, {} as Record<string, ModelInfo[]>);

  // Get current model info
  const currentModelInfo = models.find(m => m.id === currentModel);
  const displayName = currentModelInfo?.name || currentModel?.split('/')[1] || 'Select model';
  const providerColor = currentModelInfo ? PROVIDER_COLORS[currentModelInfo.provider] || 'text-content-secondary' : 'text-content-secondary';

  if (loading) {
    return (
      <div className={`flex items-center gap-1.5 ${compact ? 'text-xs' : 'text-sm'} text-content-tertiary`}>
        <Loader2 className="w-3 h-3 animate-spin" />
        <span>Loading...</span>
      </div>
    );
  }

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Selector Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        disabled={changing}
        className={`
          flex items-center gap-1.5 px-2 py-1 rounded-lg
          border border-edge-subtle bg-surface-secondary
          hover:bg-surface-tertiary hover:border-edge-medium
          transition-all cursor-pointer
          ${compact ? 'text-xs' : 'text-sm'}
          ${changing ? 'opacity-50 cursor-wait' : ''}
        `}
      >
        {changing ? (
          <Loader2 className="w-3 h-3 animate-spin text-neon-cyan" />
        ) : (
          <Cpu className={`w-3 h-3 ${providerColor}`} />
        )}
        <span className="text-content-secondary max-w-[150px] truncate">
          {displayName}
        </span>
        <ChevronDown className={`w-3 h-3 text-content-tertiary transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {/* Dropdown */}
      {isOpen && (
        <div className="absolute top-full mt-1 right-0 z-50 min-w-[280px] max-h-[400px] overflow-y-auto
                        bg-surface-elevated border border-edge-subtle rounded-xl shadow-2xl">
          {Object.entries(modelsByProvider).map(([provider, providerModels]) => (
            <div key={provider}>
              {/* Provider Header */}
              <div className="px-3 py-2 text-xs font-semibold text-content-tertiary bg-surface-tertiary/50 sticky top-0">
                {PROVIDER_NAMES[provider] || provider}
              </div>
              {/* Models */}
              {providerModels.map(model => (
                <button
                  key={model.id}
                  onClick={() => selectModel(model.id)}
                  className={`
                    w-full flex items-center gap-2 px-3 py-2 text-left text-sm
                    hover:bg-surface-tertiary transition-colors
                    ${model.id === currentModel ? 'bg-neon-cyan/10' : ''}
                  `}
                >
                  <Cpu className={`w-3.5 h-3.5 flex-shrink-0 ${PROVIDER_COLORS[provider] || 'text-content-secondary'}`} />
                  <span className="flex-1 truncate text-content-secondary">
                    {model.name}
                  </span>
                  {model.id === currentModel && (
                    <Check className="w-4 h-4 text-neon-cyan flex-shrink-0" />
                  )}
                </button>
              ))}
            </div>
          ))}

          {models.length === 0 && (
            <div className="px-3 py-4 text-sm text-content-tertiary text-center">
              No models available.
              <br />
              <span className="text-xs">
                Make sure OpenCode is running.
              </span>
            </div>
          )}
        </div>
      )}

      {/* Error Toast */}
      {error && (
        <div className="absolute top-full mt-1 right-0 z-50 px-3 py-2 bg-rose-500/20 border border-rose-500/30 rounded-lg text-xs text-rose-400">
          {error}
          <button
            onClick={() => setError(null)}
            className="ml-2 text-rose-300 hover:text-rose-100"
          >
            ×
          </button>
        </div>
      )}
    </div>
  );
}
