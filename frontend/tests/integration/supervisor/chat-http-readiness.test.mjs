// Protected sibling HTTP probe. No DOM, browser, storage or React execution.
import fs from 'node:fs';
import http from 'node:http';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import ts from 'typescript';
import {webcrypto} from 'node:crypto';
import {browserNotExecuted,validateFixtureTarget,terminalAcknowledgement,FixtureProtocolError} from '../../helpers/supervisor-fixture.mjs';
const cap=JSON.parse(fs.readFileSync(process.env.ST001_SAFE_CAP,'utf8'));
const proof=JSON.parse(fs.readFileSync('cf019-ready.json','utf8'));
if(cap.root!==process.cwd()||cap.workload!=='unit'||!cap.cf022Core||cap.lifetime!==600||proof.nonce!==cap.nonce||proof.cwd!==cap.root||proof.port!==cap.ports[0]||!['complete','cancel'].includes(cap.cf025Action))throw Error('Owned probe capability mismatch');
const origin='http://127.0.0.1:'+proof.port,deadline=Date.now()+60000;
const requests=new Set();let terminalSent=false;
async function request(target,{method='GET',body,headers={},limit=262144}={}){
 if(Date.now()>=deadline)throw Error('Probe deadline');
 return new Promise((resolve,reject)=>{
  const req=http.request({hostname:'127.0.0.1',port:proof.port,path:target,method,headers:{Host:'127.0.0.1:'+proof.port,Origin:origin,...(body===undefined?{}:{'Content-Type':'application/json'}),...headers}},res=>{
   const chunks=[];let size=0;res.on('data',data=>{size+=data.length;if(size>limit){const error=new FixtureProtocolError();reject(error);req.destroy(error);}else chunks.push(data);});
   res.on('error',reject);res.on('end',()=>{const text=Buffer.concat(chunks).toString('utf8');resolve({status:res.statusCode,headers:res.headers,text,json:()=>JSON.parse(text)});});
  });
  const timer=setTimeout(()=>req.destroy(Error('Probe absolute request deadline')),Math.max(1,Math.min(5000,deadline-Date.now())));
  requests.add(req);req.once('close',()=>{clearTimeout(timer);requests.delete(req);});req.on('error',error=>reject(typeof error.code==='string'&&error.code.startsWith('HPE_')?new FixtureProtocolError():error));
  req.setTimeout(Math.max(1,Math.min(5000,deadline-Date.now())),()=>req.destroy(Error('Probe request deadline')));
  req.end(body);
 });
}
function validators(){
 const cache={};
 function load(file){
  if(cache[file])return cache[file];const loaded={exports:{}};
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,{module:loaded,exports:loaded.exports,TextEncoder,TextDecoder,URL,URLSearchParams,crypto:webcrypto,AbortController,AbortSignal,Response,fetch:()=>{throw Error('Validator network forbidden');},require(id){if(id==='@/features/flow/lib/analysis-request')return load('src/features/flow/lib/analysis-request.ts');throw Error('Closed validator registry');}},{timeout:100});
  cache[file]=loaded.exports;return loaded.exports;
 }
 return load('src/features/supervisor/lib/supervisor-request.ts');
}
async function post(target,value,headers={}){return request(target,{method:'POST',body:JSON.stringify(value),headers:{'X-CSRF-Token':cap.nonce,...headers}});}
const httpResults={};
try{
 for(const target of ['/research','/research?supervisor_id=AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA']){
  const response=await request(target);assert.equal(response.status,200);assert.equal(response.headers['cache-control'],'no-store');assert.match(response.text,/id="app"/);assert.ok(response.headers['content-security-policy'].includes("default-src 'none'"));
 }
 for(const target of ['/research?','/research?supervisor_id=','/research?unknown=x','/research?analysis_id=aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','/research?supervisor_id=aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa&supervisor_id=aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','/research/../research','/%72esearch','/research?%73upervisor_id=x','/bundle.js?x=1','/api/auth/session?x=1','http://127.0.0.1/research','//research','/research#x'])assert.equal((await request(target)).status,422);
 assert.equal((await request('/')).status,404);assert.equal((await request('/research',{method:'POST',body:'{}'})).status,405);
 assert.equal((await request('/research',{headers:{Host:'localhost:'+proof.port}})).status,403);
 assert.equal((await request('/research',{headers:{Origin:'http://localhost:'+proof.port}})).status,403);
 for(const [target,type,limit] of [['/bundle.js','text/javascript',2097152],['/chat.css','text/css',262144]]){
  const response=await request(target,{limit});assert.equal(response.status,200);assert.equal(response.headers['content-type'],type);assert.ok(response.text.length>100);assert.equal((await request(target,{method:'POST',body:'{}'})).status,405);
 }
 const terminalNegatives=[
  [{method:'GET'},405],
  [{method:'POST',body:'{"action":"complete"}',headers:{'X-Fixture-Nonce':'wrong'}},403],
  [{method:'POST',body:'{"action":"complete"}',headers:{'X-Fixture-Nonce':cap.nonce,Origin:''}},403],
  [{method:'POST',body:'{"action":"complete","action":"cancel"}',headers:{'X-Fixture-Nonce':cap.nonce}},422],
  [{method:'POST',body:'null',headers:{'X-Fixture-Nonce':cap.nonce}},422],
  [{method:'POST',body:'x'.repeat(1025),headers:{'X-Fixture-Nonce':cap.nonce}},422],
  [{method:'POST',body:'{"action":"complete"}',headers:{'X-Fixture-Nonce':cap.nonce,'Content-Type':'text/plain'}},422],
 ];
 for(const [options,status] of terminalNegatives)assert.equal((await request('/fixture-finish',options)).status,status);
 httpResults.routes='passed';httpResults.assets='served_not_mounted';httpResults.terminal_negatives='passed';
 if(cap.cf025Action==='complete'){
  const h=validators(),root='/api/private/supervisor/core/';
  const session=(await request('/api/auth/session')).json();
  const templates=JSON.parse(fs.readFileSync('tests/fixtures/cf023-supervisor-meaning.json','utf8')).validated_plans;
  const template=templates.find(t=>t.plan.status==='ready'&&!t.draft.answers.length&&!t.draft.selected_ticker);
  assert.ok(template);const draft=h.draftValue(template.draft),pending=await h.newPreparation(draft);
  const prepare=await post(root+'preparations',pending.body);assert.equal(prepare.status,200);
  const prepared=await h.preparationValue(prepare.json().data,draft);assert.equal(prepared.state,'ready');
  const confirm=h.freshPending(draft,prepared.plan,false,prepared.plan.required_waivers,prepared.preparation_id);
  const confirmed=await post(root+'requests',confirm.confirm);assert.equal(confirmed.status,200);
  const outcome=await h.outcomeValue(confirmed.json().data);assert.equal(outcome.flow.state,'stored');
  assert.ok(session.user_id);const id=outcome.supervisor_id;
  assert.equal(validateFixtureTarget('/research?supervisor_id='+id).id,id);
  const before=(await request('/fixture-counts')).json().counts;
  const reload=await request('/research?supervisor_id='+id);assert.equal(reload.status,200);
  const loaded=await h.outcomeValue((await request(root+'requests/'+id)).json().data);
  assert.equal(h.canonical(loaded.plan),h.canonical(outcome.plan));assert.equal(loaded.supervisor_id,id);
  const after=(await request('/fixture-counts')).json().counts;
  for(const key of ['preparePOST','confirmPOST','model','provider'])assert.equal(after[key],before[key]);
  assert.equal(after.preparePOST,1);assert.equal(after.confirmPOST,1);assert.equal(after.outcomeGET,before.outcomeGET+1);
  httpResults.binding_reload='passed_explicit_GET';httpResults.reload_added_confirm_model_provider=0;
 }
 const counts=(await request('/fixture-counts')).json().counts;
 terminalSent=true;
 const {ack}=await terminalAcknowledgement(()=>post('/fixture-finish',{action:cap.cf025Action},{'X-Fixture-Nonce':cap.nonce}),cap.cf025Action);
 console.log('CF025_HTTP '+JSON.stringify({action:cap.cf025Action,ack,counts,http:httpResults,browser:browserNotExecuted()}));
}catch(error){
 // Never retransmit an uncertain terminal action. Original failure remains failure.
 if(!terminalSent){terminalSent=true;try{await post('/fixture-finish',{action:'cancel'},{'X-Fixture-Nonce':cap.nonce});}catch{/* parent checks the exact owned receipt/child */}}
 throw error;
}finally{for(const req of requests)req.destroy();}
