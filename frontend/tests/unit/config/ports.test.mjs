import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import {randomUUID} from 'node:crypto';
import ts from 'typescript';
const root=path.resolve(import.meta.dirname, '../../..');
function load(relative,{env={},fetchSpy=()=>{throw new Error('unexpected upstream');},cookie=''}={}) {
 const source=ts.transpileModule(fs.readFileSync(path.join(root,relative),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
 const bundle={exports:{}};
 vm.runInNewContext(source,{module:bundle,exports:bundle.exports,Response,Request,Headers,URL,URLSearchParams,process:{env},fetch:fetchSpy,require(name){
  if(name==='server-only')return {};
  if(name==='next/headers')return {headers:async()=>new Headers(cookie ? {Cookie:cookie} : {})};
  if(name==='./session-backend')return load('src/shared/server/session-backend.ts',{env,fetchSpy,cookie});
  if(name==='./flow-analysis-config')return load('src/shared/server/flow-analysis-config.ts',{env,fetchSpy,cookie});
  if(name==='./flow-demo-config')return load('src/shared/server/flow-demo-config.ts',{env,fetchSpy,cookie});
  if(name==='node:crypto')return {randomUUID};
  throw new Error('Unexpected import '+name);
 }});
 return bundle.exports;
}
test('dev/start use 3200 and public helper defaults to backend 8200',async()=>{
 const pkg=JSON.parse(fs.readFileSync(path.join(root,'package.json'),'utf8'));
 assert.equal(pkg.scripts.dev,'next dev -p 3200');assert.equal(pkg.scripts.start,'next start -p 3200');
 let target;
 const api=load('src/shared/api/backend.ts',{fetchSpy:async url=>{target=url;return Response.json({});}});
 await api.backendFetch('/health');assert.equal(target,'http://localhost:8200/health');
});
test('server URL missing fails closed without public URL fallback or upstream',async()=>{
 let calls=0;
 const options={env:{NEXT_PUBLIC_API_URL:'http://localhost:8200'},fetchSpy:async()=>{calls++;}};
 const backend=load('src/shared/server/session-backend.ts',options);
 assert.equal(backend.sessionBackendUrl(),null);
 assert.equal(await backend.sessionBackendFetch('/api/auth/session'),null);
 const proxy=load('src/shared/server/session-proxy.ts',options);
 assert.equal((await proxy.sessionProxy(new Request('http://localhost:3200/api/auth/session'),'/api/auth/session')).status,503);
 assert.equal(calls,0);
});
test('canonical local BFF rejects origin/Host/alias injections before upstream',async()=>{
 let calls=0;
 const proxy=load('src/shared/server/session-proxy.ts',{env:{BACKEND_URL:'http://localhost:8200'},fetchSpy:async()=>{calls++;return Response.json({});}});
 const valid={Host:'localhost:3200',Origin:'http://localhost:3200'};
 assert.equal((await proxy.sessionProxy(new Request('http://localhost:3200/api/auth/session',{headers:valid}),'/api/auth/session')).status,200);
 assert.equal(calls,1);
 for(const headers of [{...valid,Host:'localhost:3000'},{...valid,Host:'localhost:3201'},{...valid,Host:'127.0.0.1:3200'},{...valid,'X-Forwarded-Host':'evil.unit'},{...valid,Origin:'http://localhost:3000'},{...valid,Origin:'http://localhost:3201'},{...valid,Origin:'http://127.0.0.1:3200'}]) {
  assert.equal((await proxy.sessionProxy(new Request('http://localhost:3200/api/auth/session',{headers}),'/api/auth/session')).status,403);
 }
 assert.equal(calls,1);
});
