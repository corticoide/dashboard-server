import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  build: {
    outDir: '../backend/static',
    emptyOutDir: true,
    chunkSizeWarningLimit: 1000,
    rollupOptions: {
      output: {
        manualChunks: {
          'primevue': ['primevue', '@primeuix/themes'],
          'chartjs': ['chart.js'],
        },
      },
      // Exclude monaco-editor from bundling — loaded at runtime from public/
      external: ['monaco-editor'],
    },
  },
  optimizeDeps: {
    exclude: ['monaco-editor'],
  },
  server: {
    host: true,  // bind to 0.0.0.0 so LAN devices can reach the dev server
    proxy: {
      '/api': {
        target: 'https://localhost:8443',
        secure: false,
        ws: true,
      }
    }
  }
})
