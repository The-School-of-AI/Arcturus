/** @type {import('tailwindcss').Config} */
export default {
    darkMode: ["class"],
    content: ["./index.html", "./src/**/*.{ts,tsx,js,jsx}"],
    theme: {
        fontFamily: {
            sans: ['Inter', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
            mono: ['JetBrains Mono', 'SF Mono', 'Fira Code', 'monospace'],
        },
        fontSize: {
            '2xs': ['0.6875rem', { lineHeight: '1rem' }],
            'xs': ['0.75rem', { lineHeight: '1rem' }],
            'sm': ['0.8125rem', { lineHeight: '1.25rem' }],
            'base': ['0.875rem', { lineHeight: '1.5rem' }],
            'lg': ['1rem', { lineHeight: '1.5rem' }],
            'xl': ['1.25rem', { lineHeight: '1.75rem' }],
            '2xl': ['1.5rem', { lineHeight: '2rem' }],
            '3xl': ['1.875rem', { lineHeight: '2.25rem' }],
            '4xl': ['2.25rem', { lineHeight: '2.5rem' }],
        },
        extend: {
            colors: {
                border: 'hsl(var(--border))',
                input: 'hsl(var(--input))',
                ring: 'hsl(var(--ring))',
                background: 'hsl(var(--background))',
                foreground: 'hsl(var(--foreground))',
                primary: {
                    DEFAULT: 'hsl(var(--primary))',
                    foreground: 'hsl(var(--primary-foreground))'
                },
                secondary: {
                    DEFAULT: 'hsl(var(--secondary))',
                    foreground: 'hsl(var(--secondary-foreground))'
                },
                destructive: {
                    DEFAULT: 'hsl(var(--destructive))',
                    foreground: 'hsl(var(--destructive-foreground))'
                },
                muted: {
                    DEFAULT: 'hsl(var(--muted))',
                    foreground: 'hsl(var(--muted-foreground))'
                },
                accent: {
                    DEFAULT: 'hsl(var(--accent))',
                    foreground: 'hsl(var(--accent-foreground))'
                },
                popover: {
                    DEFAULT: 'hsl(var(--popover))',
                    foreground: 'hsl(var(--popover-foreground))'
                },
                card: {
                    DEFAULT: 'hsl(var(--card))',
                    foreground: 'hsl(var(--card-foreground))'
                },
                success: 'hsl(var(--success))',
                warning: 'hsl(var(--warning))',
                info: 'hsl(var(--info))',
                sidebar: {
                    DEFAULT: 'hsl(var(--sidebar-bg))',
                    border: 'hsl(var(--sidebar-border))',
                    active: 'hsl(var(--sidebar-active))',
                },
                surface: {
                    0: 'hsl(var(--surface-0))',
                    1: 'hsl(var(--surface-1))',
                    2: 'hsl(var(--surface-2))',
                    3: 'hsl(var(--surface-3))',
                },
                /* Backward-compatible aliases so existing neon references don't break the build */
                neon: {
                    yellow: 'hsl(var(--primary))',
                    lime: 'hsl(var(--success))',
                    cyan: 'hsl(var(--info))',
                },
                charcoal: {
                    DEFAULT: 'hsl(var(--foreground))',
                    50: 'hsl(var(--muted))',
                    100: 'hsl(var(--muted))',
                    200: 'hsl(var(--border))',
                    300: 'hsl(var(--muted-foreground))',
                    400: 'hsl(var(--muted-foreground))',
                    500: 'hsl(var(--muted-foreground))',
                    600: 'hsl(var(--muted-foreground))',
                    700: 'hsl(var(--secondary))',
                    800: 'hsl(var(--card))',
                    900: 'hsl(var(--background))',
                    950: 'hsl(var(--background))',
                },
            },
            borderRadius: {
                lg: 'var(--radius)',
                md: 'calc(var(--radius) - 2px)',
                sm: 'calc(var(--radius) - 4px)'
            },
            spacing: {
                'sidebar': '220px',
                'sidebar-collapsed': '52px',
                'header': '44px',
            },
            boxShadow: {
                'xs': '0 1px 2px 0 rgb(0 0 0 / 0.03)',
                'popover': '0 4px 12px rgb(0 0 0 / 0.08), 0 0 0 1px rgb(0 0 0 / 0.02)',
                'modal': '0 8px 30px rgb(0 0 0 / 0.12), 0 0 0 1px rgb(0 0 0 / 0.02)',
            },
            animation: {
                'accordion-down': 'accordion-down 0.2s ease-out',
                'accordion-up': 'accordion-up 0.2s ease-out',
                'fade-in': 'fade-in 0.15s ease-out',
                'fade-out': 'fade-out 0.15s ease-out',
                'slide-up': 'slide-up 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
                'slide-down': 'slide-down 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
                'scale-in': 'scale-in 0.15s cubic-bezier(0.16, 1, 0.3, 1)',
                'spinner': 'spinner 0.75s linear infinite',
                /* Backward-compatible animation names */
                'ticker': 'ticker 10s linear infinite',
                'pulse-subtle': 'pulse-subtle 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
                'slide-fade-in': 'fade-in 0.2s ease-out',
                'modal-scale-in': 'scale-in 0.25s ease-out',
                'slide-from-right': 'slide-from-right 0.25s cubic-bezier(0.16, 1, 0.3, 1)',
                'slide-from-left': 'slide-from-left 0.25s cubic-bezier(0.16, 1, 0.3, 1)',
                'slide-from-bottom': 'slide-up 0.25s cubic-bezier(0.16, 1, 0.3, 1)',
                'slide-from-top': 'slide-down 0.25s cubic-bezier(0.16, 1, 0.3, 1)',
                'slide-el-fade': 'fade-in 0.3s ease-out both',
                'slide-el-rise': 'slide-up 0.3s cubic-bezier(0.16, 1, 0.3, 1) both',
                'slide-el-scale': 'scale-in 0.3s cubic-bezier(0.16, 1, 0.3, 1) both',
                'slide-el-count': 'scale-in 0.3s cubic-bezier(0.16, 1, 0.3, 1) both',
            },
            keyframes: {
                'accordion-down': {
                    from: { height: '0' },
                    to: { height: 'var(--radix-accordion-content-height)' }
                },
                'accordion-up': {
                    from: { height: 'var(--radix-accordion-content-height)' },
                    to: { height: '0' }
                },
                'fade-in': {
                    from: { opacity: '0' },
                    to: { opacity: '1' }
                },
                'fade-out': {
                    from: { opacity: '1' },
                    to: { opacity: '0' }
                },
                'slide-up': {
                    from: { opacity: '0', transform: 'translateY(4px)' },
                    to: { opacity: '1', transform: 'translateY(0)' }
                },
                'slide-down': {
                    from: { opacity: '0', transform: 'translateY(-4px)' },
                    to: { opacity: '1', transform: 'translateY(0)' }
                },
                'scale-in': {
                    from: { opacity: '0', transform: 'scale(0.97)' },
                    to: { opacity: '1', transform: 'scale(1)' }
                },
                'spinner': {
                    from: { transform: 'rotate(0deg)' },
                    to: { transform: 'rotate(360deg)' }
                },
                'ticker': {
                    '0%': { transform: 'translateX(100%)' },
                    '100%': { transform: 'translateX(-100%)' }
                },
                'pulse-subtle': {
                    '0%, 100%': { opacity: '1' },
                    '50%': { opacity: '0.8' }
                },
                'slide-from-right': {
                    from: { opacity: '0', transform: 'translateX(8px)' },
                    to: { opacity: '1', transform: 'translateX(0)' }
                },
                'slide-from-left': {
                    from: { opacity: '0', transform: 'translateX(-8px)' },
                    to: { opacity: '1', transform: 'translateX(0)' }
                },
            }
        }
    },
    plugins: [require("tailwindcss-animate"), require("@tailwindcss/typography")],
}
