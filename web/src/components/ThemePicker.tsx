'use client';

import { useState, useEffect } from 'react';
import { ChevronDown, Check, Palette, Sun, Moon, Contrast } from 'lucide-react';

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

interface ThemePickerProps {
  currentTheme: string;
  onThemeChange: (themeName: string) => void;
  compact?: boolean;
}

// =============================================================================
// Theme type icons
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

export default function ThemePicker({ currentTheme, onThemeChange, compact = false }: ThemePickerProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [themes, setThemes] = useState<Theme[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Load available themes
  useEffect(() => {
    const loadThemes = async () => {
      try {
        setLoading(true);
        setError(null);

        // In a real implementation, this would fetch from your API
        // For now, we'll use the built-in themes we defined
        const response = await fetch('/api/themes');
        if (!response.ok) {
          throw new Error('Failed to load themes');
        }
        const themesData = await response.json();
        setThemes(themesData);
      } catch (err) {
        console.error('Error loading themes:', err);
        setError('Failed to load themes');
        
        // Fallback to built-in themes if API fails
        setThemes([
          {
            metadata: {
              name: 'solarized_light',
              display_name: 'Solarized Light',
              description: 'Warm, eye-friendly theme designed by Ethan Schoonover',
              author: 'Ethan Schoonover',
              version: '1.0.0',
              theme_type: 'light' as const,
              category: 'system' as const,
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
              description: 'Official GitHub dark theme with excellent accessibility',
              author: 'GitHub',
              version: '1.0.0',
              theme_type: 'dark' as const,
              category: 'system' as const,
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
        ]);
      } finally {
        setLoading(false);
      }
    };

    loadThemes();
  }, []);

  // Apply theme when selection changes
  const handleThemeSelect = (themeName: string) => {
    onThemeChange(themeName);
    setIsOpen(false);
    
    // Apply theme CSS variables
    const selectedTheme = themes.find(t => t.metadata.name === themeName);
    if (selectedTheme) {
      applyTheme(selectedTheme);
    }
  };

  // Apply CSS custom properties for theme
  const applyTheme = (theme: Theme) => {
    const root = document.documentElement;
    
    // Apply theme colors as CSS custom properties
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
    
    // Set theme class on body for CSS targeting
    document.body.className = document.body.className
      .replace(/theme-\w+/g, '')
      .trim() + ` theme-${theme.metadata.theme_type}`;
    
    // Save preference to localStorage
    localStorage.setItem('selectedTheme', theme.metadata.name);
  };

  // Get current theme display name
  const getCurrentThemeDisplay = () => {
    const theme = themes.find(t => t.metadata.name === currentTheme);
    return theme?.metadata.display_name || 'Select Theme';
  };

  const currentThemeData = themes.find(t => t.metadata.name === currentTheme);

  if (compact) {
    return (
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-2 text-sm rounded-lg border border-gray-700 hover:border-gray-600 transition-colors"
        title={`Theme: ${getCurrentThemeDisplay()}`}
      >
        {currentThemeData ? getThemeIcon(currentThemeData.metadata.theme_type) : <Palette className="w-4 h-4" />}
        {!currentThemeData && <span className="hidden sm:inline">Theme</span>}
      </button>
    );
  }

  return (
    <div className="relative">
      {/* Theme Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-2 text-sm rounded-lg border border-gray-700 hover:border-gray-600 transition-colors bg-gray-800 text-gray-200"
      >
        {currentThemeData ? (
          <>
            {getThemeIcon(currentThemeData.metadata.theme_type)}
            <span>{currentThemeData.metadata.display_name}</span>
          </>
        ) : (
          <>
            <Palette className="w-4 h-4" />
            <span>Select Theme</span>
          </>
        )}
        <ChevronDown className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {/* Dropdown */}
      {isOpen && (
        <div className="absolute top-full left-0 mt-2 w-80 bg-gray-900 border border-gray-700 rounded-lg shadow-xl z-50">
          <div className="p-3 border-b border-gray-700">
            <h3 className="text-sm font-semibold text-gray-200">Choose Theme</h3>
            <p className="text-xs text-gray-400 mt-1">Select a theme for the interface</p>
          </div>

          {loading ? (
            <div className="p-4 text-center text-gray-400">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-500 mx-auto mb-2"></div>
              <div className="text-sm">Loading themes...</div>
            </div>
          ) : error ? (
            <div className="p-4 text-center text-red-400">
              <div className="text-sm">{error}</div>
            </div>
          ) : (
            <div className="max-h-96 overflow-y-auto">
              {themes.map((theme) => (
                <button
                  key={theme.metadata.name}
                  onClick={() => handleThemeSelect(theme.metadata.name)}
                  className="w-full px-4 py-3 flex items-start gap-3 hover:bg-gray-800 transition-colors border-b border-gray-800 last:border-b-0"
                >
                  {/* Theme Preview */}
                  <div className="flex-shrink-0 mt-1">
                    {getThemeIcon(theme.metadata.theme_type)}
                  </div>

                  {/* Theme Info */}
                  <div className="flex-grow text-left">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-gray-200">
                        {theme.metadata.display_name}
                      </span>
                      {theme.metadata.wcag_compliant && (
                        <span className="px-1.5 py-0.5 text-xs bg-green-900 text-green-300 rounded">
                          WCAG
                        </span>
                      )}
                      {theme.metadata.name === currentTheme && (
                        <Check className="w-4 h-4 text-green-400" />
                      )}
                    </div>
                    <p className="text-xs text-gray-400 mt-0.5">
                      {theme.metadata.description}
                    </p>
                    <div className="flex items-center gap-3 mt-2">
                      {/* Color Preview */}
                      <div className="flex gap-1">
                        <div 
                          className="w-3 h-3 rounded border border-gray-600"
                          style={{ backgroundColor: theme.colors.background }}
                          title="Background"
                        />
                        <div 
                          className="w-3 h-3 rounded border border-gray-600"
                          style={{ backgroundColor: theme.colors.primary }}
                          title="Primary"
                        />
                        <div 
                          className="w-3 h-3 rounded border border-gray-600"
                          style={{ backgroundColor: theme.colors.success }}
                          title="Success"
                        />
                        <div 
                          className="w-3 h-3 rounded border border-gray-600"
                          style={{ backgroundColor: theme.colors.error }}
                          title="Error"
                        />
                      </div>
                      
                      {/* Contrast Ratio */}
                      <span className="text-xs text-gray-500">
                        CR: {theme.metadata.contrast_ratio.toFixed(1)}:1
                      </span>
                      
                      {/* Category */}
                      <span className="text-xs px-1.5 py-0.5 bg-gray-800 text-gray-400 rounded">
                        {theme.metadata.category}
                      </span>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}

          {/* Footer */}
          <div className="p-3 border-t border-gray-700">
            <div className="flex items-center justify-between text-xs text-gray-500">
              <span>Themes are applied instantly and saved automatically</span>
              <button
                onClick={() => {
                  // Reset to system preference
                  localStorage.removeItem('selectedTheme');
                  onThemeChange('system');
                  setIsOpen(false);
                }}
                className="text-blue-400 hover:text-blue-300"
              >
                Use System
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40"
          onClick={() => setIsOpen(false)}
        />
      )}
    </div>
  );
}