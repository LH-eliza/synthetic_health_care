import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const isVercel = Boolean(process.env.VERCEL);

export default defineConfig({
  plugins: [react()],
  base: isVercel ? '/' : '/static/patient-portal/',
  define: isVercel
    ? { 'import.meta.env.VITE_DEMO_MODE': JSON.stringify('true') }
    : {},
  build: {
    outDir: isVercel
      ? path.resolve(__dirname, 'dist')
      : path.resolve(__dirname, '../static/patient-portal'),
    emptyOutDir: true,
    rollupOptions: {
      output: {
        entryFileNames: 'assets/index.js',
        chunkFileNames: 'assets/[name].js',
        assetFileNames: isVercel
          ? 'assets/[name]-[hash][extname]'
          : 'assets/[name][extname]',
      },
    },
  },
});
