// Actual Next + synthetic HTTP upstream only. No real session/PG/Google/AI evidence.
import test from 'node:test';import assert from 'node:assert/strict';import {randomUUID} from 'node:crypto';
import {ownedHTTP} from '../../helpers/safe-http.mjs';
const user='aaaaaaaa-0000-4000-8000-000000000001',run='bbbbbbbb-0000-4000-8000-000000000002';
const view={version:1,synthetic:true,mode:'synthetic_demo',run_id:run,request_id:user,attempt_id:user,input_snapshot_id:null,execution_id:null,stage:'admitted',deadline_at:null,finished_at:null,result_stored:false,result:null,result_sha256:null,failure_code:null};
function privateHeaders(response){assert.equal(response.headers.get('cache-control'),'private, no-store');const vary=new Set((response.headers.get('vary')??'').split(',').map(v=>v.trim().toLowerCase()));assert.ok(vary.has('cookie'));assert.ok(vary.has('origin'));}
async function errorResponse(response,status,code){assert.equal(response.status,status);privateHeaders(response);const body=await response.json();assert.equal(body.data,null);assert.equal(body.error.code,code);assert.match(body.request_id,/^[0-9a-f-]{36}$/);}
test('Next demo defaults closed and opt-in SSR/BFF uses fixed raw bytes, no-store and own URL',{timeout:120000},async()=>{
 for(const demo of [false,true]){
  const seen=[];const scope=await ownedHTTP((request,response)=>{
   const path=new URL(request.url,'http://synthetic.unit').pathname;const chunks=[];request.on('data',part=>chunks.push(part));request.on('end',()=>{
    seen.push({path,method:request.method,cookie:request.headers.cookie,csrf:request.headers['x-csrf-token'],origin:request.headers.origin,authorization:request.headers.authorization,owner:request.headers['x-owner-id'],user:request.headers['x-user-id'],service:request.headers['x-service-token'],raw:Buffer.concat(chunks)});
    response.setHeader('Content-Type','application/json');response.setHeader('Cache-Control','private, no-store');
    if(path==='/api/auth/session'){response.end(JSON.stringify({user_id:user,csrf_token:'synthetic-csrf'}));return;}
    response.statusCode=request.method==='POST'?202:200;response.end(JSON.stringify({request_id:randomUUID(),data:view,error:null}));
   });
  },{demo});
  try{
   const page=await fetch(scope.base+'/flow/demo?run_id='+run,{headers:{Cookie:'verith_session=synthetic'},redirect:'manual'});assert.equal(page.status,200);const html=await page.text();assert.match(page.headers.get('cache-control'),/no-store/);assert.match(html,/Flow 합성 데모/);
   const bff=scope.base+'/api/private/flow/synthetic-demo/runs';
   if(!demo){
    await errorResponse(await fetch(bff,{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}),403,'FEATURE_UNAVAILABLE');
    await errorResponse(await fetch(bff+'/'+run),403,'FEATURE_UNAVAILABLE');
    assert.equal(seen.length,0,'off SSR/POST/GET must not call application upstream');continue;
   }
   assert.ok(seen.some(v=>v.path==='/api/auth/session'));assert.ok(seen.some(v=>v.path==='/api/flow/synthetic-demo/runs/'+run));assert.ok(seen.every(v=>v.method==='GET'));
   const beforeDirect=seen.length;
   const direct=await fetch(bff+'/'+run,{headers:{Cookie:'verith_session=synthetic'}});assert.equal(direct.status,200);privateHeaders(direct);const read=await direct.json();assert.deepEqual(read.data,view);assert.equal(read.data.run_id,run);
   assert.equal(seen.length,beforeDirect+1);assert.equal(seen[beforeDirect].method,'GET');assert.equal(seen[beforeDirect].path,'/api/flow/synthetic-demo/runs/'+run);assert.equal(seen[beforeDirect].cookie,'verith_session=synthetic');
   const raw=new Uint8Array([255,123,0]);const response=await fetch(bff,{method:'POST',headers:{'Content-Type':'application/json',Cookie:'verith_session=A; verith_session=B','X-CSRF-Token':'synthetic-csrf',Origin:scope.base,Authorization:'spoof','X-Owner-Id':'spoof','X-User-Id':'spoof','X-Service-Token':'spoof'},body:raw});assert.equal(response.status,202);privateHeaders(response);assert.deepEqual((await response.json()).data,view);
   const post=seen.find(v=>v.method==='POST');assert.deepEqual(Array.from(post.raw),Array.from(raw));assert.equal(post.cookie,'verith_session=A; verith_session=B');assert.equal(post.csrf,'synthetic-csrf');assert.equal(post.origin,scope.base);
   for(const key of ['authorization','owner','user','service'])assert.equal(post[key],undefined);
   const before=seen.length;await errorResponse(await fetch(bff+'?owner=other',{method:'POST'}),422,'INPUT_INVALID');
   await errorResponse(await fetch(bff+'/not-a-run'),403,'FEATURE_UNAVAILABLE');assert.equal(seen.length,before);
  }finally{await scope.close();}
 }
});
