/** @type {import('tailwindcss').Config} */
export default {
  content: [
    '../templates/**/*.html',
    './src/**/*.{js,jsx,ts,tsx}',
  ],
  darkMode: 'class', // Enable dark mode with class strategy
  theme: {
    extend: {
      colors: {
        // DefectDojo Security UI Color Palette
        'dd-primary': {
          50: '#EFF6FF',
          100: '#DBEAFE',
          200: '#BFDBFE',
          300: '#93C5FD',
          400: '#60A5FA',
          500: '#3B82F6',  // Default primary
          600: '#2563EB',  // Hover state
          700: '#1D4ED8',
          800: '#1E40AF',
          900: '#1E3A8A',
        },
        // Severity colors
        'dd-critical': {
          50: '#FEF2F2',
          100: '#FEE2E2',
          200: '#FECACA',
          300: '#FCA5A5',
          400: '#F87171',
          500: '#EF4444',
          600: '#DC2626',  // Default
          700: '#B91C1C',
          800: '#991B1B',
          900: '#7F1D1D',
        },
        'dd-high': {
          50: '#FFF7ED',
          100: '#FFEDD5',
          200: '#FED7AA',
          300: '#FDBA74',
          400: '#FB923C',
          500: '#F97316',
          600: '#EA580C',  // Default
          700: '#C2410C',
          800: '#9A3412',
          900: '#7C2D12',
        },
        'dd-medium': {
          50: '#FFFBEB',
          100: '#FEF3C7',
          200: '#FDE68A',
          300: '#FCD34D',
          400: '#FBBF24',
          500: '#F59E0B',
          600: '#D97706',  // Default
          700: '#B45309',
          800: '#92400E',
          900: '#78350F',
        },
        'dd-low': {
          50: '#EFF6FF',
          100: '#DBEAFE',
          200: '#BFDBFE',
          300: '#93C5FD',
          400: '#60A5FA',
          500: '#3B82F6',
          600: '#2563EB',  // Default
          700: '#1D4ED8',
          800: '#1E40AF',
          900: '#1E3A8A',
        },
        'dd-info': {
          50: '#F8FAFC',
          100: '#F1F5F9',
          200: '#E2E8F0',
          300: '#CBD5E1',
          400: '#94A3B8',
          500: '#64748B',
          600: '#475569',  // Default
          700: '#334155',
          800: '#1E293B',
          900: '#0F172A',
        },
        // Semantic colors
        'dd-success': {
          50: '#F0FDF4',
          100: '#DCFCE7',
          200: '#BBF7D0',
          300: '#86EFAC',
          400: '#4ADE80',
          500: '#22C55E',
          600: '#16A34A',  // Default
          700: '#15803D',
          800: '#166534',
          900: '#14532D',
        },
        'dd-warning': {
          50: '#FEFCE8',
          100: '#FEF9C3',
          200: '#FEF08A',
          300: '#FDE047',
          400: '#FACC15',
          500: '#EAB308',
          600: '#CA8A04',  // Default
          700: '#A16207',
          800: '#854D0E',
          900: '#713F12',
        },
        'dd-danger': {
          50: '#FEF2F2',
          100: '#FEE2E2',
          200: '#FECACA',
          300: '#FCA5A5',
          400: '#F87171',
          500: '#EF4444',
          600: '#DC2626',  // Default
          700: '#B91C1C',
          800: '#991B1B',
          900: '#7F1D1D',
        },
      },
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        mono: ['"JetBrains Mono"', '"Fira Code"', 'Consolas', 'Monaco', 'monospace'],
      },
      fontSize: {
        'xs': ['0.75rem', { lineHeight: '1rem' }],
        'sm': ['0.875rem', { lineHeight: '1.25rem' }],
        'base': ['1rem', { lineHeight: '1.5rem' }],
        'lg': ['1.125rem', { lineHeight: '1.75rem' }],
        'xl': ['1.25rem', { lineHeight: '1.75rem' }],
        '2xl': ['1.5rem', { lineHeight: '2rem', letterSpacing: '-0.01em' }],
        '3xl': ['1.875rem', { lineHeight: '2.25rem', letterSpacing: '-0.02em' }],
        '4xl': ['2.25rem', { lineHeight: '2.5rem', letterSpacing: '-0.02em' }],
        '5xl': ['3rem', { lineHeight: '1', letterSpacing: '-0.03em', fontWeight: '400' }],
        '6xl': ['3.5rem', { lineHeight: '1.1', letterSpacing: '-0.03em', fontWeight: '400' }],
      },
      colors: {
        ...require('tailwindcss/defaultTheme').colors,
        // Enterprise Dark-Mode-First Palette
        'enterprise': {
          'bg-primary': '#0f1419',
          'bg-card': '#1c2128',
          'bg-elevated': '#22272e',
          'bg-hover': '#2d333b',
          'text-primary': '#F0F6FC',
          'text-secondary': '#8b949e',
          'text-muted': '#6e7681',
          'border': 'rgba(255, 255, 255, 0.1)',
        },
        // Distinctive Accent - Violet
        'accent': {
          50: '#f5f3ff',
          100: '#ede9fe',
          200: '#ddd6fe',
          300: '#c4b5fd',
          400: '#a78bfa',
          500: '#8B5CF6',
          600: '#7c3aed',
          700: '#6d28d9',
          800: '#5b21b6',
          900: '#4c1d95',
        },
        // Semantic Colors
        'success': {
          DEFAULT: '#10B981',
          dark: '#059669',
        },
        'warning': {
          DEFAULT: '#F59E0B',
          dark: '#D97706',
        },
        'error': {
          DEFAULT: '#EF4444',
          dark: '#DC2626',
        },
        'info': {
          DEFAULT: '#3B82F6',
          dark: '#2563EB',
        },
      },
      boxShadow: {
        'dd-sm': '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
        'dd': '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px -1px rgba(0, 0, 0, 0.1)',
        'dd-md': '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1)',
        'dd-lg': '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1)',
        'dd-xl': '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1)',
      },
      borderRadius: {
        'dd-sm': '0.125rem',  // 2px
        'dd': '0.25rem',      // 4px
        'dd-md': '0.375rem',  // 6px
        'dd-lg': '0.5rem',    // 8px
        'dd-xl': '0.75rem',   // 12px
        'dd-2xl': '1rem',     // 16px
      },
      spacing: {
        // 4px grid system - standard Tailwind values plus custom
        '18': '4.5rem',   // 72px
        '22': '5.5rem',   // 88px
        '30': '7.5rem',   // 120px
        '88': '22rem',    // 352px
        '128': '32rem',   // 512px
        // Card padding values
        'card': '1.5rem', // 24px - per design brief
        'card-sm': '1rem', // 16px
        'card-lg': '2rem', // 32px
      },
      animation: {
        'fade-in': 'fadeIn 0.6s ease-out',
        'slide-up': 'slideUp 0.6s ease-out',
        'scale-in': 'scaleIn 0.4s ease-out',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(20px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        scaleIn: {
          '0%': { opacity: '0', transform: 'scale(0.95)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
      },
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
    require('@tailwindcss/typography'),
    require('@tailwindcss/aspect-ratio'),
  ],
};
