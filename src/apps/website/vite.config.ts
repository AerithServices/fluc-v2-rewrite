import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react({
      babel: {
        plugins: [['babel-plugin-react-compiler']],
      },
    }),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src/apps/website/src')
    }
  }
  // build: {
  //   rollupOptions: {
  //     output: {
  //       entryFileNames: 'chunk/[name].js',
  //       chunkFileNames: 'chunk/[name].js',
  //       // chunkFileNames: 'chunk/[name]-[hash].js',
  //       assetFileNames: 'assets/[name].[ext]'
  //     }
  //   }
  // }
})
