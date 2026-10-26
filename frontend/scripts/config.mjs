import {readFileSync, existsSync} from 'node:fs';
import {resolve, dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
export const frontendDir = resolve(dirname(fileURLToPath(import.meta.url)), '..');
export const projectDir = resolve(frontendDir, '..');
export function setting(key, fallback) {
  if (process.env[key] !== undefined && process.env[key] !== '') return process.env[key];
  const file = resolve(frontendDir, '.env.local');
  if (existsSync(file)) {
    for (const line of readFileSync(file, 'utf8').split(/\r?\n/)) {
      const match = line.match(/^\s*([A-Z][A-Z0-9_]*)\s*=\s*(.*?)\s*$/);
      if (match?.[1] === key) return match[2].replace(/^['"]|['"]$/g, '');
    }
  }
  return fallback;
}
export function apiTarget() {
  const raw = setting('CAPE_RANCH_API_TARGET', setting('GHR_API_TARGET', 'http://127.0.0.1:8000'));
  const url = new URL(raw);
  if (!['http:', 'https:'].includes(url.protocol)) throw Error('CAPE_RANCH_API_TARGET must use http(s).');
  if (url.pathname !== '/' || url.search || url.hash || url.username || url.password) throw Error('CAPE_RANCH_API_TARGET must be an origin without credentials or path.');
  return url.origin;
}
export function frontendHost() { return setting('CAPE_RANCH_FRONTEND_HOST', setting('GHR_FRONTEND_HOST', '127.0.0.1')); }
export function frontendPort(defaultPort) {
  const port = Number(setting('CAPE_RANCH_FRONTEND_PORT', setting('GHR_FRONTEND_PORT', String(defaultPort))));
  if (!Number.isInteger(port) || port < 1 || port > 65535) throw Error('CAPE_RANCH_FRONTEND_PORT must be a valid port.');
  return port;
}
