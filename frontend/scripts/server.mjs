import http from 'node:http';
import https from 'node:https';
import {createReadStream, existsSync, statSync} from 'node:fs';
import {extname, resolve, relative, sep} from 'node:path';
import {fileURLToPath} from 'node:url';
import {frontendDir, projectDir, frontendHost, frontendPort, apiTarget} from './config.mjs';

const preview = process.argv.includes('--preview');
const root = preview ? resolve(frontendDir, 'dist') : projectDir;
const port = preview ? Number(process.env.CAPE_RANCH_PREVIEW_PORT || process.env.GHR_PREVIEW_PORT || 4173) : frontendPort(3000);
const host = frontendHost();
const backend = new URL(apiTarget());
const mime = {
  '.html':'text/html; charset=utf-8', '.js':'text/javascript; charset=utf-8', '.mjs':'text/javascript; charset=utf-8',
  '.css':'text/css; charset=utf-8', '.json':'application/json; charset=utf-8', '.svg':'image/svg+xml',
  '.png':'image/png', '.webp':'image/webp', '.jpg':'image/jpeg', '.jpeg':'image/jpeg', '.gif':'image/gif',
  '.ico':'image/x-icon', '.woff':'font/woff', '.woff2':'font/woff2', '.ttf':'font/ttf', '.map':'application/json',
};
if (!existsSync(resolve(root, preview ? 'index.html' : 'frontend/index.html'))) {
  throw Error(preview ? 'Production build missing. Run npm run build first.' : 'Frontend index.html not found.');
}
const srv = http.createServer((req,res) => {
  let path;
  try { path = decodeURIComponent(new URL(req.url, 'http://localhost').pathname); }
  catch {res.writeHead(400);res.end('Bad URL');return;}
  if (path === '/api' || path.startsWith('/api/')) {
    const client = backend.protocol === 'https:' ? https : http;
    const upstream = client.request({
      hostname:backend.hostname, port:backend.port || (backend.protocol==='https:'?443:80),
      method:req.method, path:req.url, headers:{...req.headers,host:backend.host},
    }, response=>{res.writeHead(response.statusCode || 502, response.headers);response.pipe(res);});
    upstream.setTimeout(30000, ()=>upstream.destroy(Error('Backend request timed out')));
    upstream.on('error', err=>{
      if (!res.headersSent) {res.writeHead(502, {'content-type':'application/json; charset=utf-8'});res.end(JSON.stringify({detail:`Backend unavailable: ${err.message}`}));}
      else res.destroy(err);
    });
    req.pipe(upstream); return;
  }
  if (['/', '/register-organization', '/staff-recovery', '/first-time-setup'].includes(path)) path = preview ? '/index.html' : '/frontend/index.html';
  const file = resolve(root, '.'+path);
  const rel = relative(root, file);
  if (rel.startsWith('..'+sep) || rel === '..' || rel.startsWith(sep)) {res.writeHead(403);res.end('Forbidden');return;}
  if (!preview && !(['/frontend/index.html', '/frontend/logo.png'].includes(path) || ['/frontend/shared/', '/frontend/pages/', '/frontend/public/'].some(prefix=>path.startsWith(prefix)))) {
    res.writeHead(404);res.end('Not found');return;
  }
  let info;
  try{info=statSync(file);}catch{res.writeHead(404);res.end('Not found');return;}
  if (!info.isFile()){res.writeHead(404);res.end('Not found');return;}
  res.setHeader('Content-Type', mime[extname(file).toLowerCase()] || 'application/octet-stream');
  res.setHeader('X-Content-Type-Options','nosniff');
  res.setHeader('Cache-Control', /\.(html|js|mjs|css)$/.test(file) ? 'no-store' : 'public, max-age=3600');
  if (req.method === 'HEAD'){res.writeHead(200);res.end();return;}
  if (req.method !== 'GET'){res.writeHead(405);res.end('Method not allowed');return;}
  createReadStream(file).on('error',()=>res.destroy()).pipe(res);
});
srv.listen(port, host, ()=>{
  console.log(`Cape Ranch frontend (${preview?'production preview':'local development'}): http://${host}:${port}`);
  console.log(`API proxy: /api/* -> ${backend.origin}`);
  if (!preview) console.log('Native server mode: refresh the browser after frontend edits (use npm run dev for Vite development).');
});
