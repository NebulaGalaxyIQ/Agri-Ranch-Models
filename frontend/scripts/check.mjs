import {existsSync, readFileSync, readdirSync} from 'node:fs';
import {resolve, dirname, extname} from 'node:path';
import {frontendDir} from './config.mjs';

const problems = [];
for (const base of ['index.html','shared/app.js','shared/api.js','shared/ui.js','shared/icons.js']) {
  if(!existsSync(resolve(frontendDir,base))) problems.push(`Required file missing: ${base}`);
}
const html=readFileSync(resolve(frontendDir,'index.html'),'utf8');
for(const url of [...html.matchAll(/(?:src|href)=["'](\/frontend\/[^"'?]+)/g)].map(x=>x[1])) {
  const file=resolve(frontendDir,'..','.'+url);
  if(!existsSync(file)) problems.push(`index.html missing referenced asset: ${url}`);
}
const pageDir=resolve(frontendDir,'pages');
let scripts=0;
for(const page of readdirSync(pageDir,{withFileTypes:true}).filter(x=>x.isDirectory())) {
  const base=resolve(pageDir,page.name);
  if (!existsSync(resolve(base,'index.js'))) problems.push(`Missing page entry: ${page.name}`);
  for (const name of readdirSync(base).filter(n=>n.endsWith('.js'))) {
    scripts++;
    const source=readFileSync(resolve(base,name),'utf8');
    for(const match of source.matchAll(/\bfrom\s+['"](\.{1,2}\/[^'"]+)['"]/g)) {
      const spec=match[1].split('?')[0];
      if(!existsSync(resolve(base,spec)))problems.push(`Unresolved import in ${page.name}/${name}: ${match[1]}`);
    }
  }
}
const modules=readdirSync(pageDir,{withFileTypes:true}).filter(x=>x.isDirectory()).length;
if(problems.length){for(const p of problems)console.error('FAIL:',p);process.exit(1);}
console.log(`Frontend integrity OK: ${modules} page modules, ${scripts} page scripts, main entry and static assets.`);
console.log('This does not verify backend connectivity or authenticated screens.');
