// =============================================================================
// Theme Types and Utilities
// =============================================================================

export interface ThemeColors {
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

export interface ThemeMetadata {
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

export interface Theme {
  metadata: ThemeMetadata;
  colors: ThemeColors;
  custom_css?: string;
}

// =============================================================================
// Fallback Themes (used when API is unavailable)
// =============================================================================

export const FALLBACK_THEMES: Theme[] = [
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
// Theme Application
// =============================================================================

/**
 * Apply a theme's colors to the document as CSS custom properties
 */
export function applyTheme(theme: Theme): void {
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
  
  // Update body class for theme type
  document.body.className = document.body.className
    .replace(/theme-\w+/g, '')
    .trim() + ` theme-${theme.metadata.theme_type}`;
}

/**
 * Apply a theme by name, fetching from API or using fallback
 */
export async function applyThemeByName(themeName: string): Promise<Theme | null> {
  // First try to find in fallback themes
  let theme = FALLBACK_THEMES.find(t => t.metadata.name === themeName);
  
  // If not found in fallbacks, try to fetch from API
  if (!theme) {
    try {
      const response = await fetch('/api/themes');
      if (response.ok) {
        const themes: Theme[] = await response.json();
        theme = themes.find(t => t.metadata.name === themeName);
      }
    } catch (err) {
      console.error('Error fetching themes:', err);
    }
  }
  
  // Apply the theme if found
  if (theme) {
    applyTheme(theme);
    return theme;
  }
  
  // Fallback to first theme if requested theme not found
  if (FALLBACK_THEMES.length > 0) {
    applyTheme(FALLBACK_THEMES[0]);
    return FALLBACK_THEMES[0];
  }
  
  return null;
}

/**
 * Initialize theme from localStorage on page load
 */
export function initializeTheme(): string {
  const savedTheme = typeof window !== 'undefined' 
    ? localStorage.getItem('selectedTheme') 
    : null;
  
  const themeName = savedTheme || 'github_dark';
  
  // Apply theme immediately (don't wait for API)
  const fallbackTheme = FALLBACK_THEMES.find(t => t.metadata.name === themeName);
  if (fallbackTheme) {
    applyTheme(fallbackTheme);
  }
  
  return themeName;
}
