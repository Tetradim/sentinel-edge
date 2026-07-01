import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');

  return {
    plugins: [react()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    define: {
      'process.env.REACT_APP_BACKEND_URL': JSON.stringify(env.REACT_APP_BACKEND_URL || ''),
    },
    server: {
      port: 3000,
      host: '0.0.0.0',
      strictPort: false,
      cors: true,
      allowedHosts: [
        'pulse-sentinel-1.cluster-5.preview.emergentcf.cloud',
        'pulse-sentinel-1.preview.emergentagent.com',
        'sentinel-edge-live.preview.emergentagent.com',
        'localhost',
        '.preview.emergentcf.cloud',
        '.preview.emergentagent.com',
      ],
    },
    optimizeDeps: {
      include: ['zustand', 'framer-motion', 'lucide-react'],
    },
    build: {
      rollupOptions: {
        output: {
          manualChunks(id) {
            const normalizedId = id.replaceAll('\\', '/');
            if (!normalizedId.includes('/node_modules/')) return undefined;

            const nodeModulePath = normalizedId.split('/node_modules/').pop() ?? normalizedId;
            const packagePath = nodeModulePath.startsWith('.vite/deps/')
              ? nodeModulePath.slice('.vite/deps/'.length)
              : nodeModulePath;
            if (
              packagePath === 'react.js' ||
              packagePath.startsWith('react/') ||
              packagePath.startsWith('react_') ||
              packagePath.startsWith('react-dom') ||
              packagePath.startsWith('scheduler/')
            ) {
              return 'vendor-react';
            }
            if (
              packagePath.startsWith('plotly') ||
              packagePath.startsWith('react-plotly') ||
              packagePath.startsWith('recharts')
            ) {
              return 'vendor-charts';
            }
            if (packagePath.startsWith('lucide-react')) return 'vendor-icons';
            if (packagePath.startsWith('framer-motion')) return 'vendor-motion';
            if (packagePath.startsWith('zustand')) return 'vendor-state';
            return 'vendor';
          },
        },
      },
    },
  };
});
