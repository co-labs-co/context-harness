/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  darkMode: ['class', '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        // Primary background colors - using CSS variables for theming
        surface: {
          primary: 'var(--surface-primary)',
          secondary: 'var(--surface-secondary)',
          tertiary: 'var(--surface-tertiary)',
          elevated: 'var(--surface-elevated)',
        },
        // Accent colors - using CSS variables for theming
        neon: {
          cyan: 'var(--accent-primary)',
          'cyan-dim': 'var(--accent-primary-dim)',
          'cyan-glow': 'var(--accent-primary-glow)',
        },
        // Warm amber accent
        amber: {
          DEFAULT: 'var(--accent-secondary)',
          dim: 'var(--accent-secondary-dim)',
        },
        // Violet accent
        violet: {
          DEFAULT: 'var(--accent-tertiary)',
          dim: 'var(--accent-tertiary-dim)',
        },
        // Text colors - using CSS variables for theming
        content: {
          primary: 'var(--text-primary)',
          secondary: 'var(--text-secondary)',
          tertiary: 'var(--text-tertiary)',
        },
        // Border colors - using CSS variables for theming
        edge: {
          subtle: 'var(--border-subtle)',
          medium: 'var(--border-medium)',
        },
        // Direct theme color access
        theme: {
          background: 'var(--theme-background)',
          foreground: 'var(--theme-foreground)',
          primary: 'var(--theme-primary)',
          secondary: 'var(--theme-secondary)',
          success: 'var(--theme-success)',
          warning: 'var(--theme-warning)',
          error: 'var(--theme-error)',
          info: 'var(--theme-info)',
          border: 'var(--theme-border)',
          muted: 'var(--theme-muted)',
          accent: 'var(--theme-accent)',
        },
      },
      fontFamily: {
        sans: ['Outfit', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      boxShadow: {
        'glow-sm': '0 0 15px -3px rgba(0, 240, 255, 0.3)',
        'glow': '0 0 30px -5px rgba(0, 240, 255, 0.4)',
        'glow-lg': '0 0 50px -10px rgba(0, 240, 255, 0.5)',
        'inner-glow': 'inset 0 0 20px -5px rgba(0, 240, 255, 0.2)',
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'gradient-mesh': `
          radial-gradient(ellipse at 20% 0%, rgba(0, 240, 255, 0.15) 0%, transparent 50%),
          radial-gradient(ellipse at 80% 100%, rgba(168, 85, 247, 0.15) 0%, transparent 50%)
        `,
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'glow-pulse': 'glow-pulse 2s ease-in-out infinite',
        'float': 'float 6s ease-in-out infinite',
      },
      keyframes: {
        'glow-pulse': {
          '0%, 100%': { boxShadow: '0 0 20px -5px rgba(0, 240, 255, 0.4)' },
          '50%': { boxShadow: '0 0 30px -5px rgba(0, 240, 255, 0.6)' },
        },
        'float': {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-10px)' },
        },
      },
      borderRadius: {
        '2xl': '1rem',
        '3xl': '1.5rem',
      },
    },
  },
  plugins: [],
};
