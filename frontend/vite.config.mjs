import {defineConfig} from 'vite';
import {frontendDir, frontendHost, frontendPort, apiTarget} from './scripts/config.mjs';

// The existing application resolves modules and photos under /frontend/.
// Rewriting /frontend/ to the frontend root preserves URLs and keeps backend code out of Vite's served directory.
const rootIndex = () => ({
  name: 'cape-ranch-root-page',
  configureServer(server) {
    server.middlewares.use((req, _res, next) => {
      if (req.url === '/' || req.url?.startsWith('/?')) {
        req.url = `/index.html${req.url.substring(1)}`;
      } else if (req.url?.startsWith('/frontend/')) {
        req.url = req.url.replace(/^\/frontend\//, '/');
      }
      next();
    });
  },
});

export default defineConfig({
  root: frontendDir,
  publicDir: false,
  plugins: [rootIndex()],
  server: {
    host: frontendHost(),
    port: frontendPort(3000),
    strictPort: true,
    fs: {strict: true, allow: [frontendDir]},
    proxy: {
      '/api': {target: apiTarget(), changeOrigin: true, secure: true, ws: false},
    },
  },
  // This project intentionally uses a static-copy build instead of vite build:
  // its dynamic /frontend/pages/<name>/index.js imports must remain deployable.
  clearScreen: false,
});
