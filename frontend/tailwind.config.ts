import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: { 950: '#102620', 900: '#17362e', 800: '#1d493d', 700: '#25614f' },
        pine: { 50: '#effbf6', 100: '#d8f5e8', 200: '#b3ead3', 300: '#81d8b7', 400: '#4abf96', 500: '#27a57d', 600: '#198465', 700: '#176a53', 800: '#155443', 900: '#124638' },
        cream: { 50: '#fffdf8', 100: '#fbf7ed', 200: '#f3ead6' },
        coral: { 400: '#fb826f', 500: '#f2634e', 600: '#d94835' },
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        display: ['Manrope', 'Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        card: '0 1px 2px rgba(16,38,32,.04), 0 12px 36px rgba(16,38,32,.07)',
        lift: '0 20px 48px rgba(16,38,32,.14)',
      },
      animation: {
        'fade-up': 'fadeUp .45s cubic-bezier(.2,.7,.2,1) both',
        'soft-pulse': 'softPulse 2.5s ease-in-out infinite',
      },
      keyframes: {
        fadeUp: { from: { opacity: '0', transform: 'translateY(8px)' }, to: { opacity: '1', transform: 'translateY(0)' } },
        softPulse: { '0%, 100%': { opacity: '.55' }, '50%': { opacity: '1' } },
      },
    },
  },
  plugins: [],
} satisfies Config
