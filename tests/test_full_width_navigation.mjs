import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const file=new URL('../frontend/shared/ui.js', import.meta.url).pathname;
let u='http://localhost:8000/?module=crops&area=fields';
const windowMock={
 location:{get href(){return u;}},
 history:{pushState(_state,_t,path){u='http://localhost:8000'+path;}},
 scrollTo(){}
};
globalThis.window=windowMock;
const ui=await import(pathToFileURL(file).href);
const sections=[{id:'fields',title:'Fields',description:'Farm fields'},{id:'cycles',title:'Crop cycles'}];
const output=ui.submoduleWorkspace('Crop Farming',sections,'fields','<div id="table">Data</div>');
assert.ok(output.includes('submodule-page'));
assert.ok(!output.includes('<nav'));
assert.ok(!output.includes('submodule-rail'));
assert.ok(output.includes('Back to')===false || output.includes('All Crop Farming areas'));
assert.ok(output.includes('id="table"'));
assert.equal(ui.rememberedSubmodule('crops'),'fields');
ui.rememberSubmodule('crops','cycles');
assert.equal(ui.rememberedSubmodule('crops'),'cycles');
assert.match(u,/area=cycles/);
ui.rememberSubmodule('crops',null);
assert.equal(ui.rememberedSubmodule('crops'),null);
assert.doesNotMatch(u,/area=/);
const cards=ui.submoduleDirectory('Crop Farming',sections,{fields:5});
assert.match(cards,/data-submodule="fields"/);
assert.doesNotMatch(cards,/<nav/);
console.log('SUBMODULE_NAVIGATION_OK independent full width pages + addressable route + directory');
