/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        void: '#0a0a0a',
        honeycomb: '#2a2a2a',
        amber: {
          DEFAULT: '#e88a1e',
          light: '#f0a040',
          dark: '#c06a10'
        },
        warm: '#f0e6d0',
        chlorophyll: '#6ab04c',
        wheat: '#f0932b',
        blood: '#eb4d4b'
      },
      fontFamily: {
        orbitron: ['Orbitron', 'sans-serif'],
        inter: ['Inter', 'sans-serif'],
        jetbrains: ['JetBrains Mono', 'monospace']
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'glow': 'glow 2s ease-in-out infinite alternate',
        'float': 'float 6s ease-in-out infinite'
      },
      keyframes: {
        glow: {
          '0%': { boxShadow: '0 0 5px #e88a1e, 0 0 10px #e88a1e, 0 0 15px #e88a1e' },
          '100%': { boxShadow: '0 0 10px #e88a1e, 0 0 20px #e88a1e, 0 0 30px #e88a1e' }
        },
        float: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-10px)' }
        }
      }
    },
  },
  plugins: [],
}
