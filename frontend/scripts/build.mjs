import {cpSync, copyFileSync, existsSync, mkdirSync, readFileSync, rmSync, writeFileSync, statSync} from 'node:fs';
import {resolve} from 'node:path';
import {frontendDir} from './config.mjs';

const dist = resolve(frontendDir, 'dist');
const target = resolve(dist, 'frontend');
for (const required of ['index.html', 'shared/app.js', 'shared/api.js', 'pages', 'public']) {
  if (!existsSync(resolve(frontendDir, required))) throw Error(`Missing frontend source: ${required}`);
}
rmSync(dist, {recursive: true, force: true});
mkdirSync(target, {recursive: true});
for (const name of ['shared', 'pages', 'public']) {
  cpSync(resolve(frontendDir, name), resolve(target, name), {recursive: true, force: true});
}
for (const name of ['index.html', 'logo.png']) {
  if (existsSync(resolve(frontendDir, name))) copyFileSync(resolve(frontendDir, name), resolve(target, name));
}
copyFileSync(resolve(frontendDir, 'index.html'), resolve(dist, 'index.html'));
const html = readFileSync(resolve(dist, 'index.html'), 'utf8');
if (!html.includes('/frontend/shared/app.js') || !html.includes('id="app"')) throw Error('Invalid application entry HTML.');
writeFileSync(resolve(dist, 'build-info.json'), JSON.stringify({
  app: 'Cape Ranch',
  built_at: new Date().toISOString(),
  strategy: 'preserve-original-es-modules-and-assets',
  pages: (await import('node:fs')).readdirSync(resolve(target, 'pages'), {withFileTypes:true}).filter(e=>e.isDirectory()).map(e=>e.name),
}, null, 2));
console.log(`Built static frontend: ${dist}`);
console.log(`Entry: ${resolve(dist, 'index.html')}`);
console.log('All existing modules and photographs copied without rewriting their paths.');
