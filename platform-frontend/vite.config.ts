import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  envDir: "../",
  server: {
    port: 5173,
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    rollupOptions: {
      output: {
        // Split heavy vendor libraries into separate chunks so they're cached
        // independently and don't bloat the main bundle.
        manualChunks: {
          'vendor-react': ['react', 'react-dom'],
          'vendor-monaco': ['@monaco-editor/react', 'monaco-editor'],
          'vendor-pdf': ['@react-pdf-viewer/core', '@react-pdf-viewer/default-layout'],
          'vendor-graph': ['reactflow', 'vis-network', 'vis-data'],
          'vendor-tiptap': ['@tiptap/react', '@tiptap/starter-kit'],
          'vendor-terminal': ['xterm', 'xterm-addon-fit', 'xterm-addon-web-links'],
          'vendor-ui': ['recharts', 'mermaid'],
        },
      },
    },
    chunkSizeWarningLimit: 1000,
  },
})
