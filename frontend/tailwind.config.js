/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{js,jsx,ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        bg: { primary: '#0d1117', secondary: '#161b22', tertiary: '#21262d' },
        border: '#30363d',
        text: { primary: '#c9d1d9', secondary: '#8b949e', muted: '#484f58' },
        accent: { blue: '#58a6ff', green: '#3fb950', red: '#f85149', yellow: '#d29922', purple: '#a371f7' },
      },
      fontFamily: { sans: ['Inter', 'sans-serif'], mono: ['JetBrains Mono', 'monospace'] },
    },
  },
  plugins: [],
};
