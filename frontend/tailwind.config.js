/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        telegram: {
          bg: '#17212b',
          sidebar: '#0e1621',
          hover: '#202b36',
          active: '#2b5278',
          text: '#ffffff',
          textSecondary: '#6d7883',
          accent: '#5288c1',
          green: '#4dcd5e',
          blue: '#3390ec',
        }
      }
    },
  },
  plugins: [],
}
