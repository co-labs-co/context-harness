'use client';

import { useState, useEffect } from 'react';
import { X, Settings, Palette, Cpu, Sun, Moon, Contrast, Check, ChevronDown } from 'lucide-react';

// =============================================================================
// Types
// =============================================================================

interface ThemeColors {
  background: string;
  foreground: string;
  primary: string;
  secondary: string;
  success: string;
  warning: string;
  error: string;
  info: string;
  border: string;
  muted: string;
  accent: string;
}

interface ThemeMetadata {
  name: string;
  display_name: string;
  description: string;
  author: string;
  version: string;
  theme_type: 'light' | 'dark' | 'high_contrast';
  category: 'system' | 'custom' | 'accessibility';
  wcag_compliant: boolean;
  contrast_ratio: number;
  has_transparency: boolean;
  supports_transitions: boolean;
}

interface Theme {
  metadata: ThemeMetadata;
  colors: ThemeColors;
  custom_css?: string;
}

interface ModelInfo {
  id: string;
  provider: string;
  name: string;
  display_name: string;
}

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentTheme: string;
  onThemeChange: (themeName: string) => void;
  defaultModel: string;
  onDefaultModelChange: (modelId: string) => void;
}

// =============================================================================
// Constants
// =============================================================================

const PROVIDER_COLORS: Record<string, string> = {
  'anthropic': 'text-orange-400',
  'openai': 'text-emerald-400',
  'github-copilot': 'text-blue-400',
  'google': 'text-yellow-400',
  'aws-bedrock': 'text-amber-500',
  'azure': 'text-sky-400',
};

const PROVIDER_NAMES: Record<string, string> = {
  'anthropic': 'Anthropic',
  'openai': 'OpenAI',
  'github-copilot': 'GitHub Copilot',
  'google': 'Google',
  'aws-bedrock': 'AWS Bedrock',
  'azure': 'Azure OpenAI',
};

const FALLBACK_THEMES: Theme[] = [
  {
    metadata: {
      name: 'solarized_light',
      display_name: 'Solarized Light',
      description: 'Warm, eye-friendly light theme',
      author: 'Ethan Schoonover',
      version: '1.0.0',
      theme_type: 'light',
      category: 'system',
      wcag_compliant: true,
      contrast_ratio: 7.0,
      has_transparency: false,
      supports_transitions: true,
    },
    colors: {
      background: '#fdf6e3',
      foreground: '#657b83',
      primary: '#268bd2',
      secondary: '#93a1a1',
      success: '#859900',
      warning: '#b58900',
      error: '#dc322f',
      info: '#2aa198',
      border: '#93a1a1',
      muted: '#839496',
      accent: '#268bd2',
    },
  },
  {
    metadata: {
      name: 'github_dark',
      display_name: 'GitHub Dark',
      description: 'Official GitHub dark theme',
      author: 'GitHub',
      version: '1.0.0',
      theme_type: 'dark',
      category: 'system',
      wcag_compliant: true,
      contrast_ratio: 9.5,
      has_transparency: false,
      supports_transitions: true,
    },
    colors: {
      background: '#0d1117',
      foreground: '#c9d1d9',
      primary: '#58a6ff',
      secondary: '#8b949e',
      success: '#3fb950',
      warning: '#d29922',
      error: '#f85149',
      info: '#58a6ff',
      border: '#30363d',
      muted: '#8b949e',
      accent: '#58a6ff',
    },
  },
];

// =============================================================================
// Helper Components
// =============================================================================

const getThemeIcon = (themeType: string) => {
  switch (themeType) {
    case 'light':
      return <Sun className="w-4 h-4" />;
    case 'dark':
      return <Moon className="w-4 h-4" />;
    case 'high_contrast':
      return <Contrast className="w-4 h-4" />;
    default:
      return <Palette className="w-4 h-4" />;
  }
};

// =============================================================================
// Component
// =============================================================================

export function SettingsModal({
  isOpen,
  onClose,
  currentTheme,
  onThemeChange,
  defaultModel,
  onDefaultModelChange,
}: SettingsModalProps) {
  const [themes, setThemes] = useState<Theme[]>(FALLBACK_THEMES);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [loadingThemes, setLoadingThemes] = useState(true);
  const [loadingModels, setLoadingModels] = useState(true);
  const [activeTab, setActiveTab] = useState<'appearance' | 'models'>('appearance');

  // Load themes
  useEffect(() => {
    if (!isOpen) return;
    
    const loadThemes = async () => {
      try {
        setLoadingThemes(true);
        const response = await fetch('/api/themes');
        if (response.ok) {
          const data = await response.json();
          setThemes(data.length > 0 ? data : FALLBACK_THEMES);
        }
      } catch (err) {
        console.error('Error loading themes:', err);
      } finally {
        setLoadingThemes(false);
      }
    };
    loadThemes();
  }, [isOpen]);

  // Load models
  useEffect(() => {
    if (!isOpen) return;
    
    const loadModels = async () => {
      try {
        setLoadingModels(true);
        const response = await fetch('/api/chat/models');
        if (response.ok) {
          const data = await response.json();
          setModels(data.models || []);
        }
      } catch (err) {
        console.error('Error loading models:', err);
      } finally {
        setLoadingModels(false);
      }
    };
    loadModels();
  }, [isOpen]);

  // Apply theme
  const handleThemeSelect = (themeName: string) => {
    onThemeChange(themeName);
    const selectedTheme = themes.find(t => t.metadata.name === themeName);
    if (selectedTheme) {
      applyTheme(selectedTheme);
    }
  };

  const applyTheme = (theme: Theme) => {
    const root = document.documentElement;
    root.style.setProperty('--theme-background', theme.colors.background);
    root.style.setProperty('--theme-foreground', theme.colors.foreground);
    root.style.setProperty('--theme-primary', theme.colors.primary);
    root.style.setProperty('--theme-secondary', theme.colors.secondary);
    root.style.setProperty('--theme-success', theme.colors.success);
    root.style.setProperty('--theme-warning', theme.colors.warning);
    root.style.setProperty('--theme-error', theme.colors.error);
    root.style.setProperty('--theme-info', theme.colors.info);
    root.style.setProperty('--theme-border', theme.colors.border);
    root.style.setProperty('--theme-muted', theme.colors.muted);
    root.style.setProperty('--theme-accent', theme.colors.accent);
    
    document.body.className = document.body.className
      .replace(/theme-\w+/g, '')
      .trim() + ` theme-${theme.metadata.theme_type}`;
    
    localStorage.setItem('selectedTheme', theme.metadata.name);
  };

  // Group models by provider
  const modelsByProvider = models.reduce((acc, model) => {
    if (!acc[model.provider]) {
      acc[model.provider] = [];
    }
    acc[model.provider].push(model);
    return acc;
  }, {} as Record<string, ModelInfo[]>);

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-black/60 z-50 animate-in fade-in duration-200"
        onClick={onClose}
      />
      
      {/* Modal */}
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none">
        <div 
          className="bg-surface-elevated border border-edge-subtle rounded-2xl shadow-2xl 
                     w-full max-w-2xl max-h-[80vh] overflow-hidden pointer-events-auto
                     animate-in zoom-in-95 fade-in duration-200"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-edge-subtle">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-neon-cyan/20 to-violet/20 
                            flex items-center justify-center border border-neon-cyan/30">
                <Settings className="w-5 h-5 text-neon-cyan" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-content-primary">Settings</h2>
                <p className="text-xs text-content-tertiary">Customize your experience</p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-2 text-content-tertiary hover:text-content-primary 
                       hover:bg-surface-tertiary rounded-lg transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Tabs */}
          <div className="flex border-b border-edge-subtle">
            <button
              onClick={() => setActiveTab('appearance')}
              className={`flex items-center gap-2 px-6 py-3 text-sm font-medium transition-colors
                ${activeTab === 'appearance' 
                  ? 'text-neon-cyan border-b-2 border-neon-cyan' 
                  : 'text-content-tertiary hover:text-content-secondary'}`}
            >
              <Palette className="w-4 h-4" />
              Appearance
            </button>
            <button
              onClick={() => setActiveTab('models')}
              className={`flex items-center gap-2 px-6 py-3 text-sm font-medium transition-colors
                ${activeTab === 'models' 
                  ? 'text-neon-cyan border-b-2 border-neon-cyan' 
                  : 'text-content-tertiary hover:text-content-secondary'}`}
            >
              <Cpu className="w-4 h-4" />
              Default Model
            </button>
          </div>

          {/* Content */}
          <div className="p-6 overflow-y-auto max-h-[calc(80vh-180px)]">
            {activeTab === 'appearance' && (
              <div className="space-y-4">
                <div>
                  <h3 className="text-sm font-medium text-content-primary mb-1">Theme</h3>
                  <p className="text-xs text-content-tertiary mb-4">
                    Choose a color theme for the interface
                  </p>
                </div>

                {loadingThemes ? (
                  <div className="flex items-center justify-center py-8">
                    <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-neon-cyan" />
                  </div>
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {themes.map((theme) => (
                      <button
                        key={theme.metadata.name}
                        onClick={() => handleThemeSelect(theme.metadata.name)}
                        className={`flex items-start gap-3 p-4 rounded-xl border transition-all text-left
                          ${theme.metadata.name === currentTheme 
                            ? 'border-neon-cyan bg-neon-cyan/10' 
                            : 'border-edge-subtle hover:border-edge-medium hover:bg-surface-tertiary'}`}
                      >
                        {/* Theme Icon */}
                        <div className={`p-2 rounded-lg ${theme.metadata.name === currentTheme ? 'bg-neon-cyan/20 text-neon-cyan' : 'bg-surface-tertiary text-content-secondary'}`}>
                          {getThemeIcon(theme.metadata.theme_type)}
                        </div>

                        {/* Theme Info */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium text-content-primary">
                              {theme.metadata.display_name}
                            </span>
                            {theme.metadata.name === currentTheme && (
                              <Check className="w-4 h-4 text-neon-cyan" />
                            )}
                          </div>
                          <p className="text-xs text-content-tertiary mt-0.5 truncate">
                            {theme.metadata.description}
                          </p>
                          
                          {/* Color Preview */}
                          <div className="flex items-center gap-2 mt-2">
                            <div className="flex gap-1">
                              <div 
                                className="w-4 h-4 rounded border border-edge-subtle"
                                style={{ backgroundColor: theme.colors.background }}
                                title="Background"
                              />
                              <div 
                                className="w-4 h-4 rounded border border-edge-subtle"
                                style={{ backgroundColor: theme.colors.primary }}
                                title="Primary"
                              />
                              <div 
                                className="w-4 h-4 rounded border border-edge-subtle"
                                style={{ backgroundColor: theme.colors.success }}
                                title="Success"
                              />
                              <div 
                                className="w-4 h-4 rounded border border-edge-subtle"
                                style={{ backgroundColor: theme.colors.error }}
                                title="Error"
                              />
                            </div>
                            {theme.metadata.wcag_compliant && (
                              <span className="px-1.5 py-0.5 text-[10px] bg-emerald-500/20 text-emerald-400 rounded">
                                WCAG
                              </span>
                            )}
                          </div>
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}

            {activeTab === 'models' && (
              <div className="space-y-4">
                <div>
                  <h3 className="text-sm font-medium text-content-primary mb-1">Default Model</h3>
                  <p className="text-xs text-content-tertiary mb-4">
                    Select the default AI model for new chat sessions
                  </p>
                </div>

                {loadingModels ? (
                  <div className="flex items-center justify-center py-8">
                    <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-neon-cyan" />
                  </div>
                ) : models.length === 0 ? (
                  <div className="text-center py-8 text-content-tertiary">
                    <Cpu className="w-8 h-8 mx-auto mb-2 opacity-50" />
                    <p className="text-sm">No models available</p>
                    <p className="text-xs mt-1">Make sure OpenCode is running</p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {Object.entries(modelsByProvider).map(([provider, providerModels]) => (
                      <div key={provider}>
                        <h4 className={`text-xs font-medium mb-2 ${PROVIDER_COLORS[provider] || 'text-content-secondary'}`}>
                          {PROVIDER_NAMES[provider] || provider}
                        </h4>
                        <div className="space-y-2">
                          {providerModels.map((model) => (
                            <button
                              key={model.id}
                              onClick={() => onDefaultModelChange(model.id)}
                              className={`w-full flex items-center gap-3 p-3 rounded-xl border transition-all text-left
                                ${model.id === defaultModel 
                                  ? 'border-neon-cyan bg-neon-cyan/10' 
                                  : 'border-edge-subtle hover:border-edge-medium hover:bg-surface-tertiary'}`}
                            >
                              <Cpu className={`w-4 h-4 flex-shrink-0 ${PROVIDER_COLORS[provider] || 'text-content-secondary'}`} />
                              <span className="flex-1 text-sm text-content-secondary">
                                {model.name}
                              </span>
                              {model.id === defaultModel && (
                                <Check className="w-4 h-4 text-neon-cyan flex-shrink-0" />
                              )}
                            </button>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                <div className="pt-4 border-t border-edge-subtle">
                  <p className="text-xs text-content-tertiary">
                    💡 The default model will be used for all new chat sessions. 
                    You can still change the model per-session using the model selector.
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="px-6 py-4 border-t border-edge-subtle bg-surface-secondary/50">
            <div className="flex items-center justify-between">
              <p className="text-xs text-content-tertiary">
                Settings are saved automatically
              </p>
              <button
                onClick={onClose}
                className="px-4 py-2 text-sm font-medium text-content-primary 
                         bg-surface-tertiary hover:bg-surface-secondary 
                         border border-edge-subtle rounded-lg transition-colors"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
