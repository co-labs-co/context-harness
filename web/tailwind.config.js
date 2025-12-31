/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  darkMode: ['class', '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        // Primary background colors
        surface: {
          primary: '#0a0a0f',
          secondary: '#12121a',
          tertiary: '#1a1a24',
          elevated: '#22222e',
        },
        // Neon cyan accent
        neon: {
          cyan: '#00f0ff',
          'cyan-dim': 'rgba(0, 240, 255, 0.2)',
          'cyan-glow': 'rgba(0, 240, 255, 0.4)',
        },
        // Warm amber accent
        amber: {
          DEFAULT: '#ffb800',
          dim: 'rgba(255, 184, 0, 0.2)',
        },
        // Violet accent
        violet: {
          DEFAULT: '#a855f7',
          dim: 'rgba(168, 85, 247, 0.2)',
        },
        // Text colors
        content: {
          primary: '#f0f0f5',
          secondary: '#9090a0',
          tertiary: '#606070',
        },
        // Border colors
        edge: {
          subtle: '#2a2a38',
          medium: '#3a3a48',
        },
        // Theme colors (will be overridden by CSS custom properties)
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
