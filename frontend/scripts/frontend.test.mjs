import {test} from 'node:test';
import assert from 'node:assert/strict';
import {existsSync, readFileSync, mkdirSync, writeFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {frontendDir, projectDir, setting, apiTarget} from './config.mjs';

test('existing app entry and modules are preserved', ()=>{
  const html=readFileSync(resolve(frontendDir,'index.html'),'utf8');
  assert.match(html, /\/frontend\/shared\/app\.js/);
  assert.match(html, /id="app"/);
  for(const p of ['shared/api.js','shared/ui.js','pages/fattening/index.js','pages/crops/index.js','pages/livestock/index.js','pages/analytics/index.js']){
    assert.ok(existsSync(resolve(frontendDir,p)),p);
  }
});
test('local backend proxy has safe origin defaults', ()=>{
  const api = apiTarget();
  assert.match(api,/^https?:\/\//);
  assert.ok(!api.includes('@'));
});
test('frontend and deployment entrypoints retain absolute asset paths', ()=>{
  const vite=readFileSync(resolve(frontendDir,'vite.config.mjs'),'utf8');
  const builder=readFileSync(resolve(frontendDir,'scripts/build.mjs'),'utf8');
  assert.match(vite,/req\.url\?\.startsWith\('\/frontend\/'\)/);
  assert.match(builder,/copyFileSync\(resolve\(frontendDir, 'index.html'\)/);
  assert.match(vite,/['"]\/api['"]/);
});
