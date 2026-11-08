// Actual Next + synthetic HTTP upstream only. No real session/PG/Google/AI evidence.
import test from 'node:test';import assert from 'node:assert/strict';import {randomUUID} from 'node:crypto';
import {ownedHTTP} from '../../helpers/safe-http.mjs';
const user='aaaaaaaa-0000-4000-8000-000000000001',run='bbbbbbbb-0000-4000-8000-000000000002';
const view={version:1,synthetic:true,mode:'synthetic_demo',run_id:run,request_id:user,attempt_id:user,input_snapshot_id:null,execution_id:null,stage:'admitted',deadline_at:null,finished_at:null,result_stored:false,result:null,result_sha256:null,failure_code:null};
test('Next demo defaults closed and opt-in SSR/BFF uses fixed raw bytes, no-store and own URL',{timeout:120000},async()=>{
 for(const demo of [false,true]){
  const seen=[];const scope=await ownedHTTP((request,response)=>{
   const path=new URL(request.url,'http://synthetic.unit').pathname;const chunks=[];request.on('data',part=>chunks.push(part));request.on('end',()=>{
    seen.push({path,method:request.method,cookie:request.headers.cookie,csrf:request.headers['x-csrf-token'],authorization:request.headers.authorization,raw:Buffer.concat(chunks)});
    response.setHeader('Content-Type','application/json');response.setHeader('Cache-Control','private, no-store');
    if(path==='/api/auth/session'){response.end(JSON.stringify({user_id:user,csrf_token:'synthetic-csrf'}));return;}
    response.end(JSON.stringify({request_id:randomUUID(),data:view,error:null}));
   });
  },{demo});
  try{
   const page=await fetch(scope.base+'/flow/demo?run_id='+run,{headers:{Cookie:'verith_session=synthetic'},redirect:'manual'});const html=await page.text();assert.match(page.headers.get('cache-control'),/no-store/);assert.match(html,/Flow 합성 데모/);
   if(!demo){assert.equal(seen.length,0);continue;}
   assert.ok(seen.some(v=>v.path==='/api/auth/session'));assert.ok(seen.some(v=>v.path==='/api/flow/synthetic-demo/runs/'+run));assert.ok(seen.every(v=>v.method==='GET'));
   const raw=new Uint8Array([255,123,0]);const response=await fetch(scope.base+'/api/private/flow/synthetic-demo/runs',{method:'POST',headers:{'Content-Type':'application/json',Cookie:'verith_session=A; verith_session=B','X-CSRF-Token':'synthetic-csrf',Authorization:'spoof'},body:raw});assert.equal(response.status,200);assert.equal(response.headers.get('cache-control'),'private, no-store');
   const post=seen.find(v=>v.method==='POST');assert.deepEqual(Array.from(post.raw),Array.from(raw));assert.equal(post.cookie,'verith_session=A; verith_session=B');assert.equal(post.authorization,undefined);
   const before=seen.length;assert.equal((await fetch(scope.base+'/api/private/flow/synthetic-demo/runs?owner=other',{method:'POST'})).status,422);assert.equal(seen.length,before);
  }finally{await scope.close();}
 }
});
