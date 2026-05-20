import type { Config } from 'tailwindcss';
import animate from 'tailwindcss-animate';

/**
 * Eldir - Tailwind config.
 * Tokens issus de DA/tokens.css (Direction 1 · Mission Control).
 * Référence centrale : `--eldir-*` CSS vars définies dans src/styles/tokens.css.
 */
const config: Config = {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    container: {
      center: true,
      padding: '1rem',
      screens: { '2xl': '1400px' },
    },
    extend: {
      colors: {
        eldir: {
          orange: 'hsl(var(--eldir-orange) / <alpha-value>)',
          'orange-soft': 'hsl(var(--eldir-orange-soft) / <alpha-value>)',
          cream: 'hsl(var(--eldir-cream) / <alpha-value>)',
          'cream-2': 'hsl(var(--eldir-cream-2) / <alpha-value>)',
          paper: 'hsl(var(--eldir-paper) / <alpha-value>)',
          ink: 'hsl(var(--eldir-ink) / <alpha-value>)',
          'ink-2': 'hsl(var(--eldir-ink-2) / <alpha-value>)',
          gray: 'hsl(var(--eldir-gray) / <alpha-value>)',
          'gray-2': 'hsl(var(--eldir-gray-2) / <alpha-value>)',
          'gray-3': 'hsl(var(--eldir-gray-3) / <alpha-value>)',
          gold: 'hsl(var(--eldir-gold) / <alpha-value>)',
          green: 'hsl(var(--eldir-green) / <alpha-value>)',
          amber: 'hsl(var(--eldir-amber) / <alpha-value>)',
          red: 'hsl(var(--eldir-red) / <alpha-value>)',
          blue: 'hsl(var(--eldir-blue) / <alpha-value>)',
        },
        // shadcn/ui aliases - mappés sur les tokens Eldir.
        background: 'hsl(var(--background) / <alpha-value>)',
        foreground: 'hsl(var(--foreground) / <alpha-value>)',
        card: {
          DEFAULT: 'hsl(var(--card) / <alpha-value>)',
          foreground: 'hsl(var(--card-foreground) / <alpha-value>)',
        },
        primary: {
          DEFAULT: 'hsl(var(--primary) / <alpha-value>)',
          foreground: 'hsl(var(--primary-foreground) / <alpha-value>)',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary) / <alpha-value>)',
          foreground: 'hsl(var(--secondary-foreground) / <alpha-value>)',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted) / <alpha-value>)',
          foreground: 'hsl(var(--muted-foreground) / <alpha-value>)',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent) / <alpha-value>)',
          foreground: 'hsl(var(--accent-foreground) / <alpha-value>)',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive) / <alpha-value>)',
          foreground: 'hsl(var(--destructive-foreground) / <alpha-value>)',
        },
        border: 'hsl(var(--border) / <alpha-value>)',
        input: 'hsl(var(--input) / <alpha-value>)',
        ring: 'hsl(var(--ring) / <alpha-value>)',
      },
      fontFamily: {
        sans: ['Inter', 'Helvetica Neue', 'Helvetica', 'Arial', 'sans-serif'],
        mono: ['JetBrains Mono', 'SF Mono', 'Menlo', 'Consolas', 'monospace'],
      },
      fontSize: {
        // échelle dense Mission Control (mono = labels caps)
        '2xs': ['9px', { lineHeight: '1' }],
        xxs: ['10px', { lineHeight: '1.1' }],
      },
      borderRadius: {
        // DA D1 = coins quasi droits (3px), pas de SaaS rounded-2xl
        eldir: '3px',
        sm: '2px',
        md: '4px',
      },
      letterSpacing: {
        caps: '0.08em',
        wider: '0.1em',
      },
      keyframes: {
        'pulse-orange': {
          '0%': { boxShadow: '0 0 0 0 hsl(var(--eldir-orange) / 0.5)' },
          '70%': { boxShadow: '0 0 0 8px hsl(var(--eldir-orange) / 0)' },
          '100%': { boxShadow: '0 0 0 0 hsl(var(--eldir-orange) / 0)' },
        },
      },
      animation: {
        'pulse-orange': 'pulse-orange 1.6s ease-out infinite',
      },
    },
  },
  plugins: [animate],
};

export default config;
