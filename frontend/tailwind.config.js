/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'Neue Haas Grotesk', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'IBM Plex Mono', 'monospace'],
      },
      colors: {
        swiss: {
          accent: '#0047FF',     // Azul Klein Suizo
          black: '#0A0A0A',
          charcoal: '#121214',
          surface: '#F8F9FA',
          muted: '#71717A',
          border: '#E4E4E7',
          'border-dark': '#27272A',
        }
      },
      borderRadius: {
        none: '0px',
        sm: '2px',
        DEFAULT: '2px',
      },
      borderWidth: {
        DEFAULT: '1px',
      }
    },
  },
  plugins: [],
}
