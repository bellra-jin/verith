import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import vm from 'node:vm';
import ts from 'typescript';
import {createRequire} from 'node:module';
import {independentCleanup,expiryCleanup} from '../helpers/safe-http.mjs';
import {readSource,sourceAllowed} from '../../scripts/check-local-ports.mjs';
const require=createRequire(import.meta.url);
test('CF008 exact fresh inputs preserve private route exception and adjacent denial',()=>{
 for(const file of ['src/shared/server/flow-demo-config.ts','src/app/flow/demo/page.tsx','src/features/flow/components/synthetic-demo.tsx','src/features/flow/lib/synthetic-demo.ts','tests/unit/flow/synthetic-demo.test.mjs','tests/integration/bff/synthetic-demo-http.test.mjs']){assert.equal(sourceAllowed(file),true);assert.ok(readSource(process.cwd(),file).length>0);}
 assert.equal(sourceAllowed('src/app/api/private/adjacent/route.ts'),false);
 const source=fs.readFileSync(path.join(process.cwd(),'scripts/check-local-ports.mjs'),'utf8');assert.match(source,/unit\/flow\/synthetic-demo\.test\.mjs/);assert.match(source,/integration\/bff\/synthetic-demo-http\.test\.mjs/);
});
test('CF005 exact helper, fixture and unit are copied without adjacent JSON grants',()=>{
 for(const name of ['src/features/flow/lib/observation-window.ts','tests/fixtures/cf005-observation-cases.json','tests/unit/flow/observation.test.mjs']){
  assert.equal(sourceAllowed(name),true);
  assert.ok(readSource(process.cwd(),name).length>0);
 }
 assert.equal(sourceAllowed('tests/fixtures/adjacent.json'),false);
 const source=fs.readFileSync(path.join(process.cwd(),'src/features/flow/components/flow-report-view.tsx'),'utf8');
 assert.match(source,/const daily = safeDaily\(s\)/);
 assert.match(source,/observationWindow\(s, RECENT_DAYS, TREND_DAYS\)/);
 assert.match(source,/window\.status === "sufficient_rows"/);
 assert.match(source,/window\.interpretationNotice/);
 assert.ok(source.indexOf('const daily = safeDaily(s)')<source.indexOf('daily.flatMap'));
 assert.doesNotMatch(source,/Number\(row\[name\] \?\? 0\)/);
});
test('Technical unknown metadata preserves nullish defaults and valid values without inventing numbers',()=>{
 const source=fs.readFileSync(path.join(process.cwd(),'src/features/technical/components/indicator-card.tsx'),'utf8');
 const parsed=ts.createSourceFile('indicator-card.tsx',source,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);
 const helpers=parsed.statements.filter(node=>ts.isFunctionDeclaration(node)&&node.name?.text==='annotationText');
 assert.equal(helpers.length,1);
 // Compile only the reviewed pure helper, never the component, React or application imports.
 const helper=helpers[0];
 function noEffects(node){
  assert.equal(ts.isCallExpression(node)||ts.isNewExpression(node)||ts.isPropertyAccessExpression(node)||ts.isElementAccessExpression(node),false);
  ts.forEachChild(node,noEffects);
 }
 noEffects(helper);
 const js=ts.transpileModule(helper.getText(parsed),{compilerOptions:{target:ts.ScriptTarget.ES2022}}).outputText;
 const display=vm.runInNewContext(js+'\nannotationText;',Object.create(null),{timeout:100});
 for(const fallback of ['5MA▲20MA','28','72']){
  for(const value of [null,undefined])assert.equal(display(value,fallback),fallback);
  for(const value of [0,28,-1,72.5,'','20MA▲60MA','28'])assert.equal(display(value,fallback),value);
  for(const value of [true,false,[],['28'],{}, {rsi:28},1n])assert.equal(display(value,fallback),null);
 }
 for(const field of ['ma5','ma20','ma60']){
  assert.ok(source.includes(`typeof row.${field} === "number" && row.${field} ? formatNumber(row.${field}) : ""`));
 }
});
test('copy selection rejects private/untracked shapes and unsafe source identities',()=>{
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'synthetic-copy-'));
 try{
  fs.writeFileSync(path.join(root,'valid.ts'),'synthetic');
  assert.equal(readSource(root,'valid.ts').toString(),'synthetic');
  fs.symlinkSync(path.join(root,'valid.ts'),path.join(root,'alias.ts'));
  fs.linkSync(path.join(root,'valid.ts'),path.join(root,'hard.ts'));
  for(const p of ['alias.ts','hard.ts','../escape.ts','.env.synthetic','server.key'])assert.throws(()=>readSource(root,p));
  for(const p of ['public/server.key','src/private.pem','public/database.sql','untracked.ts'])assert.equal(sourceAllowed(p),false);
 }finally{fs.rmSync(root,{recursive:true});}
});
test('preload rejects collection-time private/DNS/TCP/UDP/process probes',()=>{
 assert.ok(process.env.ST001_SAFE_CAP,'must run through owned OS-protected entry');
 assert.equal(process.env.OPENSSL_CONF,'/dev/null');
 const {install,expected}=require('../../scripts/safe-checks-guard.cjs');assert.equal(typeof install,'function');
 const {deniedFileLabel}=require('../../scripts/safe-checks-guard.cjs');
 assert.equal(deniedFileLabel('/synthetic/project/package.json','/owned','/synthetic/project/node_modules'),'original-project-root:package.json');
 assert.equal(deniedFileLabel('/synthetic/project/other/package.json','/owned','/synthetic/project/node_modules'),'original-project:public-manifest-relative-location-redacted');
 assert.equal(deniedFileLabel('/synthetic/secret-name.txt','/owned','/dependency'),'outside:target-redacted');
 assert.equal(deniedFileLabel('/synthetic/credentials/token.json','/owned','/dependency'),'private-path-redacted');
 assert.equal(deniedFileLabel('/synthetic/.env.local','/owned','/dependency'),'private-path-redacted');
 expected(()=>fs.readFileSync('.env.synthetic'));
 expected(()=>require('node:dns').resolve('synthetic.invalid'));
 expected(()=>require('node:net').connect({host:'127.0.0.1',port:1}));
 expected(()=>require('node:dgram').createSocket('udp4'));
 expected(()=>require('node:child_process').execFileSync('/usr/bin/true'));
 expected(()=>require('node:child_process').spawn(process.execPath,[path.join(process.cwd(),'node_modules/next/dist/bin/next')],{cwd:process.cwd(),env:{NODE_OPTIONS:process.env.NODE_OPTIONS,ST001_SAFE_CAP:process.env.ST001_SAFE_CAP,OPENSSL_CONF:'/synthetic/unapproved'}}));
 for(const key of ['GOOGLE_CLIENT_SECRET','DATABASE_URL','DYLD_INSERT_LIBRARIES','PYTHONPATH','PYTEST_PLUGINS'])assert.equal(process.env[key],undefined);
});

test('stop failure does not skip listener cleanup; retries only incomplete owned actions',async()=>{
 let stops=0,listeners=0;
 const cleanup=independentCleanup([
  ['child',async()=>{stops++;if(stops===1)throw Error('synthetic stop failure');}],
  ['listener',async()=>{listeners++;}],
 ]);
 await assert.rejects(cleanup(),AggregateError);
 assert.equal(stops,1);assert.equal(listeners,1);
 await Promise.all([cleanup(),cleanup()]);
 assert.equal(stops,2);assert.equal(listeners,1);
 await cleanup();assert.equal(stops,2);assert.equal(listeners,1);
});
test('expiry captures cleanup rejection and propagates explicit failure',async()=>{
 let callback,observed,attempts=0;
 expiryCleanup(async()=>{attempts++;throw Error('synthetic timeout stop failure');},error=>{observed=error;},1,fn=>{callback=fn;return {};});
 callback();await new Promise(resolve=>setImmediate(resolve));
 assert.equal(attempts,1);assert.ok(observed instanceof AggregateError);
 assert.match(observed.message,/cleanup failure/);
});

test('exact installed Next fork plan pins module/IPC/preload and drops injected env',()=>{
 const {forkPlan}=require('../../scripts/safe-checks-guard.cjs');
 const cap={root:process.cwd(),dependency:path.join(process.cwd(),'node_modules'),guard:path.join(process.cwd(),'scripts/safe-checks-guard.cjs'),environment:{LANG:'en_US.UTF-8',ST001_SAFE_CAP:process.env.ST001_SAFE_CAP,GOOGLE_CLIENT_SECRET:'SYNTHETIC-DO-NOT-PASS'}};
 const target=fs.realpathSync(path.join(cap.dependency,'next/dist/compiled/jest-worker/processChild.js'));
 const options={cwd:cap.root,env:{ST001_SAFE_CAP:process.env.ST001_SAFE_CAP,JEST_WORKER_ID:'1',IS_NEXT_WORKER:'true',NODE_OPTIONS:'--require=/synthetic/unapproved.cjs'},execArgv:[],silent:true};
 const plan=forkPlan(target,[],options,cap);
 assert.equal(plan.module,target);assert.deepEqual(plan.args,[]);assert.deepEqual(plan.options.stdio,['pipe','pipe','pipe','ipc']);
 assert.equal(plan.options.env.OPENSSL_CONF,'/dev/null');assert.equal(plan.options.env.GOOGLE_CLIENT_SECRET,undefined);assert.equal(plan.options.env.NODE_OPTIONS,'--require='+cap.guard);assert.equal(plan.options.detached,false);
 for(const change of [{detached:true},{execArgv:['--eval=unexpected']},{execPath:'/bin/sh'},{stdio:'inherit'},{env:{}}])assert.throws(()=>forkPlan(target,[],{...options,...change},cap));
 assert.throws(()=>forkPlan(target,['unexpected'],options,cap));assert.throws(()=>forkPlan(import.meta.filename,[],options,cap));
});
test('tracked private directory names are rejected before file contents are opened',()=>{
 assert.equal(sourceAllowed('src/app/api/private/[...path]/route.ts'),true);
 for(const p of ['src/app/api/private/other.ts','src/app/api/private/keys/token.ts'])assert.equal(sourceAllowed(p),false);
 for(const p of ['src/secrets/token.ts','src/keys/fixture.ts','src/private/data.ts','src/dumps/cache.ts','src/backups/copy.ts','src/logs/data.ts']){
  assert.equal(sourceAllowed(p),false);assert.throws(()=>readSource('/no-such-synthetic-root',p),/unsafe source name/);
 }
});
test('fake 200 or nonce/PID/cwd mismatch never becomes ready; early exit fails',async()=>{
 const {validateReady,pollOwnedReady}=await import('../helpers/safe-http.mjs');
 const receipt={nonce:'synthetic-nonce',pid:123,cwd:'/owned',alive:true};
 for(const proof of [{},{status:200},{...receipt,nonce:'other'},{...receipt,pid:124},{...receipt,cwd:'/other'}])assert.throws(()=>validateReady(proof,receipt));
 assert.throws(()=>validateReady(receipt,{...receipt,alive:false}));
 let probes=0;
 await assert.rejects(pollOwnedReady({alive:()=>false,owns:()=>true,proof:async()=>{probes++;return receipt;},receipt}),/exited/);
 assert.equal(probes,0);
 let tick=0;
 await assert.rejects(pollOwnedReady({alive:()=>true,owns:()=>false,proof:async()=>{probes++;return receipt;},receipt,now:()=>tick,sleep:async n=>{tick+=n;},timeout:5}),/timeout/);
 assert.equal(probes,0,'do not probe an unowned fake listener');
 await pollOwnedReady({alive:()=>true,owns:()=>true,proof:async()=>receipt,receipt});
});
test('bind/spawn-equivalent rejection keeps independent listener cleanup and failure',async()=>{
 const {listen}=await import('../helpers/safe-http.mjs');
 const {EventEmitter}=await import('node:events');
 const server=new EventEmitter();server.listen=()=>queueMicrotask(()=>server.emit('error',Error('synthetic bind failure')));
 await assert.rejects(listen(server,3200,'localhost'),/bind failure/);
 let listenerClosed=false;
 const cleanup=independentCleanup([['spawned child',async()=>{throw Error('synthetic spawn/receipt failure');}],['listener',async()=>{listenerClosed=true; }]]);
 await assert.rejects(cleanup());assert.equal(listenerClosed,true);
});
test('leader exit still retires group; TERM -> KILL waits for actual group disappearance',async()=>{
 const {retireGroup}=await import('../../scripts/check-local-ports.mjs');
 const signals=[];let waits=0,direct=0;
 await retireGroup({exists:()=>true,owned:()=>true,signal:s=>signals.push(s),waitGroup:async()=>++waits===2,waitDirect:async()=>{direct++;}});
 assert.deepEqual(signals,['SIGTERM','SIGKILL']);assert.equal(direct,1);
 await assert.rejects(retireGroup({exists:()=>true,owned:()=>false,signal:()=>assert.fail('must not signal foreign group'),waitGroup:async()=>true,waitDirect:async()=>{}}),/ownership/);
 await assert.rejects(retireGroup({exists:()=>true,owned:()=>true,signal:()=>{},waitGroup:async()=>false,waitDirect:async()=>{}}),/survived KILL/);
});
test('root replacement refuses cleanup and preserves synthetic sibling',async()=>{
 const {ownedRoot}=await import('../../scripts/check-local-ports.mjs');
 const parent=fs.mkdtempSync(path.join(os.tmpdir(),'root-replacement-')),sibling=path.join(parent,'sibling');fs.mkdirSync(sibling);
 const owned=ownedRoot(parent),saved=owned.root+'-original';
 try{
  fs.renameSync(owned.root,saved);fs.mkdirSync(owned.root);
  assert.throws(()=>owned.close(),/ownership mismatch/);assert.ok(fs.existsSync(sibling));assert.ok(fs.existsSync(saved));
 }finally{fs.rmSync(parent,{recursive:true});}
});

test('signal cleanup attempts all receipts and retains failed group for retry',async()=>{
 const {abortOwned}=await import('../../scripts/check-local-ports.mjs');
 const first={},second={},children=new Set([first,second]),seen=[];
 await assert.rejects(abortOwned(children,async child=>{seen.push(child);if(child===first)throw Error('synthetic signal failure');}),AggregateError);
 assert.equal(seen.length,2);assert.deepEqual([...children],[first]);
 await abortOwned(children,async()=>{});assert.equal(children.size,0);
});
test('command nonzero/timeout/spawn error cannot become success and always retires receipt',async()=>{
 const {command}=await import('../../scripts/check-local-ports.mjs');
 const {EventEmitter}=await import('node:events');
 const fake=()=>Object.assign(new EventEmitter(),{pid:123,exitCode:7,signalCode:null,stdout:new EventEmitter(),stderr:new EventEmitter()});
 let retired=0;
 await assert.rejects(command(['synthetic-command'],{root:process.cwd(),env:{},launch:fake,wait:async()=>{},retire:async()=>{retired++;}}),/failed 7/);
 await assert.rejects(command(['synthetic-command'],{root:process.cwd(),env:{},launch:fake,wait:async()=>{throw Error('synthetic timeout');},retire:async()=>{retired++;}}),/timeout/);
 assert.equal(retired,2);
 await assert.rejects(command(['synthetic-command'],{root:process.cwd(),env:{},launch:()=>{throw Error('synthetic spawn failure');}}),/spawn failure/);
});

test('zero collection and skip/failure output cannot be reported as success',async()=>{
 const {validateTestOutput}=await import('../../scripts/check-local-ports.mjs');
 assert.equal(validateTestOutput('# tests 2\n# pass 2\n# fail 0\n# skipped 0'),2);
 for(const output of ['','# tests 0','# tests 2\n# skipped 1','# tests 2\n# fail 1','# tests 2\n# cancelled 1','# tests 2\n# todo 1'])assert.throws(()=>validateTestOutput(output));
});

test('native protection needs true and allowed cat controls; signal/init/non-permission failures reject',async()=>{
 const {validNativeProbe,verifyNativeSequence}=await import('../../scripts/check-local-ports.mjs');
 const result=(status=0,stdout='',stderr='',signal=null)=>({status,stdout,stderr,signal});
 assert.equal(validNativeProbe('true',result(),'/synthetic'),true);
 assert.equal(validNativeProbe('allowed',result(0,'SYNTHETIC-ALLOWED\n'),'/synthetic'),true);
 const permission='cat: /synthetic: Permission denied\n';
 assert.equal(validNativeProbe('denied',result(1,'',permission),'/synthetic'),true);
 for(const bad of [result(null,'','','SIGABRT'),result(1),result(2,'',permission),result(1,'unexpected',permission),result(1,'','loader failed'),result(1,'',permission,'SIGTERM')])assert.equal(validNativeProbe('denied',bad,'/synthetic'),false);
 assert.equal(validNativeProbe('allowed',result(1,'',permission),'/synthetic'),false);
 const stages=[['true','true'],['allowed','allowed'],['denied','denied']],calls=[];
 await assert.rejects(verifyNativeSequence(stages,async command=>{calls.push(command);return result(null,'','','SIGABRT');},'/synthetic'));
 assert.deepEqual(calls,['true']);calls.length=0;
 await assert.rejects(verifyNativeSequence(stages,async command=>{calls.push(command);throw Error('synthetic timeout');},'/synthetic'),/timeout/);
 assert.deepEqual(calls,['true']);
});

test('single metadata response preserves three APIs, context, encoding and Buffer isolation without raw IO',async()=>{
 const {packageResponder}=require('../../scripts/safe-checks-guard.cjs');
 const bytes=Buffer.from('{"name":"synthetic-metadata"}'),literal='/synthetic-outside/package.json',denied=[];
 const snapshot=packageResponder(bytes,literal,'synthetic-fingerprint',kind=>{denied.push(kind);throw Error('SAFE_CHECK_DENIED: '+kind);});
 bytes.fill(0);
 assert.equal(snapshot.matches(literal),true);assert.equal(snapshot.matches(literal+'/../package.json'),false);
 const raw=fs.openSync;let originalOpens=0;
 fs.openSync=function(value,...args){if(value===literal){originalOpens++;throw Error('raw original must never open');}return raw.call(this,value,...args);};
 try{
  const first=snapshot.sync(literal);assert.equal(first.toString(),'{"name":"synthetic-metadata"}');first.fill(0);
  assert.equal(snapshot.sync(literal,'utf8'),'{"name":"synthetic-metadata"}');
  assert.equal(snapshot.sync(literal,{encoding:'hex',flag:'r'}),Buffer.from('{"name":"synthetic-metadata"}').toString('hex'));
  let returned=false;
  const callback=new Promise((resolve,reject)=>snapshot.callback(literal,(error,data)=>{try{assert.equal(returned,true);if(error)reject(error);else resolve(data);}catch(failure){reject(failure);}}));returned=true;
  assert.equal((await callback).toString(),'{"name":"synthetic-metadata"}');
  assert.equal(await new Promise((resolve,reject)=>snapshot.callback(literal,'utf8',(error,data)=>error?reject(error):resolve(data))),'{"name":"synthetic-metadata"}');
  const promise=snapshot.promise(literal);assert.ok(promise instanceof Promise);assert.equal((await promise).toString(),'{"name":"synthetic-metadata"}');
  assert.equal(await snapshot.promise(literal,{encoding:'utf8'}),'{"name":"synthetic-metadata"}');
  const abort=new AbortController();abort.abort();
  await assert.rejects(snapshot.promise(literal,{signal:abort.signal}),{name:'AbortError',code:'ABORT_ERR'});
  await assert.rejects(new Promise((resolve,reject)=>snapshot.callback(literal,{signal:abort.signal},error=>error?reject(error):resolve())),{code:'ABORT_ERR'});
  const mid=new AbortController(),pending=snapshot.promise(literal,{signal:mid.signal});mid.abort();await assert.rejects(pending,{code:'ABORT_ERR'});
  for(const value of ['/synthetic-outside/other/package.json','/package.json','/synthetic-outside/package-lock.json','/synthetic-outside/.env',literal+'/../package.json',new URL('file:///synthetic-outside/package.json'),Buffer.from(literal),3])assert.throws(()=>snapshot.sync(value),/SAFE_CHECK_DENIED/);
  for(const options of [{flag:'w'},{flag:0},{encoding:'invalid'},{signal:{}},{unknown:true}])await assert.rejects(snapshot.promise(literal,options),/SAFE_CHECK_DENIED/);
  assert.throws(()=>snapshot.sync(literal,{signal:abort.signal}),/SAFE_CHECK_DENIED/);
  assert.equal(originalOpens,0);assert.ok(denied.length>0);assert.equal('rawOriginalReadCalls' in snapshot.ledger(),false,'responder has no raw-consumer observation');
  assert.deepEqual(Object.keys(snapshot.ledger().hits),['readFile','readFileSync','promisesReadFile']);
 }finally{fs.openSync=raw;}
});

test('worker snapshot validates identity/hash and rejects corruption, aliases and raw original operations',async()=>{
 const guard=require('../../scripts/safe-checks-guard.cjs'),{manifestIdentity,loadPackageSnapshot,expected}=guard;
 const cap=JSON.parse(fs.readFileSync(process.env.ST001_SAFE_CAP,'utf8'));
 const folder=fs.mkdtempSync(path.join(os.tmpdir(),'snapshot-fixture-')),snapshot=path.join(folder,'package.json');
 const bytes=fs.readFileSync(path.join(process.cwd(),'package.json'));
 let rawOriginalOpens=0;
 const io={...fs,openSync(value,...args){if(value===cap.packageSnapshot.literal){rawOriginalOpens++;throw Error('original raw read attempted');}return fs.openSync(value,...args);}};
 const fixture=()=>({...cap,root:folder,packageSnapshot:{...cap.packageSnapshot,snapshot,snapshotIdentity:manifestIdentity(snapshot)}});
 try{
  fs.writeFileSync(snapshot,bytes);
  assert.deepEqual(loadPackageSnapshot(fixture(),io),bytes);assert.equal(rawOriginalOpens,0);
  for(const change of [{literal:path.join(path.dirname(cap.packageSnapshot.literal),'other/package.json')},{sha256:'0'.repeat(64)},{length:0},{snapshot:path.join(folder,'alias.json')},{sourceRoot:'/synthetic/unapproved'},{extra:true}])assert.throws(()=>loadPackageSnapshot({...fixture(),packageSnapshot:{...fixture().packageSnapshot,...change}},io),/SAFE_CHECK_DENIED/);
  assert.throws(()=>loadPackageSnapshot({...cap,packageSnapshot:undefined},io),/SAFE_CHECK_DENIED/);
  let record=fixture();fs.unlinkSync(snapshot);fs.writeFileSync(snapshot,bytes);assert.throws(()=>loadPackageSnapshot(record,io),/SAFE_CHECK_DENIED/);
  fs.writeFileSync(snapshot,Buffer.alloc(bytes.length));assert.throws(()=>loadPackageSnapshot(fixture(),io),/SAFE_CHECK_DENIED/);
  fs.unlinkSync(snapshot);fs.symlinkSync(path.join(process.cwd(),'package.json'),snapshot);assert.throws(()=>manifestIdentity(snapshot),/SAFE_CHECK_DENIED/);fs.unlinkSync(snapshot);
  fs.writeFileSync(snapshot,bytes);fs.linkSync(snapshot,path.join(folder,'hard'));assert.throws(()=>manifestIdentity(snapshot),/SAFE_CHECK_DENIED/);fs.unlinkSync(path.join(folder,'hard'));
  record=fixture();fs.unlinkSync(snapshot);assert.throws(()=>loadPackageSnapshot(record,io));
  // The installed mapping serves bytes only. Other APIs and alias spellings stay denied.
  const literal=cap.packageSnapshot.literal;
  const esm=await import('node:fs'),before=guard.observation();
  const originalOpen=fs.openSync;let mappingOriginalOpenCalls=0;
  fs.openSync=function(value,...args){if(value===literal){mappingOriginalOpenCalls++;throw Error('mapping raw source open');}return originalOpen.call(this,value,...args);};
  try{
   const response=fs.readFileSync(literal);assert.deepEqual(response,bytes);response.fill(0);
   assert.deepEqual(esm.readFileSync(literal),bytes);
   assert.deepEqual(await fs.promises.readFile(literal),bytes);
   assert.deepEqual(await new Promise((resolve,reject)=>fs.readFile(literal,(error,data)=>error?reject(error):resolve(data))),bytes);
   assert.equal(mappingOriginalOpenCalls,0);
  }finally{fs.openSync=originalOpen;}
  const after=guard.observation();
  assert.equal(after.rawDispatches,before.rawDispatches,'installed mapping never dispatches to a raw fs consumer');
  assert.equal(after.rawOriginalDispatches,before.rawOriginalDispatches);
  assert.equal(after.native,'not-observed');
  assert.equal(after.snapshot.hits.readFileSync-before.snapshot.hits.readFileSync,2);
  assert.equal(after.snapshot.hits.readFile-before.snapshot.hits.readFile,1);
  assert.equal(after.snapshot.hits.promisesReadFile-before.snapshot.hits.promisesReadFile,1);
  fs.readFileSync(path.join(process.cwd(),'package.json'));
  assert.ok(guard.observation().rawDispatches>after.rawDispatches,'raw consumer counter must actually increment for owned reads');
  for(const value of [path.dirname(literal)+'/./package.json',new URL('file://'+literal),path.join(path.dirname(literal),'package-lock.json'),path.join(path.dirname(literal),'next.config.ts')])expected(()=>fs.readFileSync(value));
  expected(()=>fs.openSync(literal,'r'));expected(()=>fs.createReadStream(literal));expected(()=>fs.writeFileSync(literal,'synthetic-must-not-write'));
  assert.ok(guard.observation().rawOriginalDenied>=after.rawOriginalDenied+2,'denials are observed and never erased by expected-negative handling');
  assert.equal(guard.observation().rawOriginalDispatches,after.rawOriginalDispatches);
  assert.equal(rawOriginalOpens,0);
 }finally{fs.rmSync(folder,{recursive:true});}
});

test('controller package pre/post checks reject source/snapshot/root drift and retire command receipts',async()=>{
 const {packageRecord,manifestIdentity,checkedCommand,command,ownedRoot}=await import('../../scripts/check-local-ports.mjs');
 const {EventEmitter}=await import('node:events');
 const bytes=fs.readFileSync(path.join(process.cwd(),'package.json'));
 async function scenario({phase='after',mutate=()=>{},exit=0,fails=false,replaced=false}){
  const directory=fs.mkdtempSync(path.join(os.tmpdir(),'controller-package-'));
  const sourceRoot=path.join(directory,'source'),dependency=path.join(sourceRoot,'node_modules'),sibling=path.join(directory,'sibling');
  fs.mkdirSync(dependency,{recursive:true});fs.mkdirSync(sibling);
  const owned=ownedRoot(directory),root=owned.root,literal=path.join(sourceRoot,'package.json'),snapshot=path.join(root,'package.json');
  fs.writeFileSync(literal,bytes);fs.writeFileSync(snapshot,bytes);
  const record=packageRecord(root,dependency,bytes,manifestIdentity(literal),sourceRoot),children=new Set();
  let launches=0,retires=0,sourceOpens=0,prepared=0;
  const rawOpen=fs.openSync;
  fs.openSync=function(value,...args){const flags=args[0],readOnly=flags==='r'||typeof flags==='number'&&!(flags&(fs.constants.O_WRONLY|fs.constants.O_RDWR|fs.constants.O_CREAT));if(value===literal&&readOnly)sourceOpens++;return rawOpen.call(this,value,...args);};
  const state={literal,snapshot,root,sourceRoot,bytes};
  try{
   if(phase==='before')mutate(state);
   const run=()=>checkedCommand({record,root,dependency,argv:['synthetic-command'],env:{},timeout:1,children,prepare(){prepared++;},
    invoke:(argv,options)=>command(argv,{...options,launch(){launches++;return Object.assign(new EventEmitter(),{pid:123,exitCode:exit,signalCode:null,stdout:new EventEmitter(),stderr:new EventEmitter()});},
     wait:async()=>{if(phase==='after')mutate(state);},retire:async()=>{retires++;}})});
   if(fails)await assert.rejects(run());else assert.equal(await run(),'');
   assert.equal(launches,phase==='before'?0:1);assert.equal(prepared,launches);assert.equal(retires,launches);assert.equal(children.size,0);
   assert.equal(sourceOpens,phase==='before'?0:fails&&exit===0?1:exit!==0&&phase==='after'&&replaced?1:2);
   assert.ok(fs.existsSync(sibling),'unrelated synthetic sibling survives command cleanup');
   if(replaced)assert.throws(()=>owned.close(),/ownership mismatch/);else{owned.close();assert.equal(fs.existsSync(root),false);}
  }finally{fs.openSync=rawOpen;fs.rmSync(directory,{recursive:true});}
 }
 await scenario({});
 await scenario({phase:'before',fails:true,mutate:({literal})=>fs.writeFileSync(literal,'synthetic-drift')});
 await scenario({phase:'before',fails:true,mutate:({snapshot})=>fs.writeFileSync(snapshot,'synthetic-drift')});
 await scenario({fails:true,mutate:({literal})=>fs.writeFileSync(literal,'synthetic-drift')});
 await scenario({fails:true,mutate:({snapshot})=>fs.writeFileSync(snapshot,'synthetic-drift')});
 await scenario({fails:true,mutate:({sourceRoot,bytes})=>{fs.renameSync(sourceRoot,sourceRoot+'-original');fs.mkdirSync(path.join(sourceRoot,'node_modules'),{recursive:true});fs.writeFileSync(path.join(sourceRoot,'package.json'),bytes);}});
 await scenario({fails:true,replaced:true,mutate:({root,bytes})=>{fs.renameSync(root,root+'-original');fs.mkdirSync(root);fs.writeFileSync(path.join(root,'package.json'),bytes);}});
 await scenario({exit:7,fails:true});
 await scenario({exit:7,fails:true,replaced:true,mutate:({root,bytes})=>{fs.renameSync(root,root+'-original');fs.mkdirSync(root);fs.writeFileSync(path.join(root,'package.json'),bytes);}});
});

function syntheticDiagnosticContext(key='11'.repeat(32)){
 return {root:'/owned',dependency:'/verified/node_modules',runtime:['/runtime'],sourceRoot:'/reviewed/project',workerRole:'entry-worker',workload:'self-test',diagnostics:{key,run:'22'.repeat(12),copySources:['package.json','src/lib/public.ts','src/app/api/private/[...path]/route.ts','src/secrets/not-public.ts']}};
}
test('diagnostics use exact public labels and per-run HMAC without extra IO or raw names',()=>{
 const {createDiagnostics}=require('../../scripts/safe-checks-guard.cjs'),context=syntheticDiagnosticContext();
 const originals=new Map(),names=['openSync','readFileSync','readFile','readlinkSync','statSync','lstatSync','existsSync','readdirSync'];let calls=0;
 for(const name of names){originals.set(name,fs[name]);fs[name]=()=>{calls++;throw Error('diagnostic IO forbidden');};}
 try{
  const first=createDiagnostics(context),second=createDiagnostics({...context,workerRole:'next-worker'}),other=createDiagnostics({...context,diagnostics:{...context.diagnostics,key:'33'.repeat(32),run:'44'.repeat(12)}});
  const input={lexical:'/SYNTHETIC_PERSON/credentials/PRIVATE_NAME.pem',canonical:'/SYNTHETIC_PERSON/credentials/PRIVATE_NAME.pem',api:'readFile',stack:'Error: SYNTHETIC_PRIVATE_ERROR\nat /SYNTHETIC_PERSON/private/caller.js:1:1'};
  const one=first.describe(input),two=second.describe(input),three=other.describe(input);
  assert.equal(one.targetId,two.targetId);assert.notEqual(one.targetId,three.targetId);assert.equal(one.privateNameMatch,true);assert.equal(one.role,'outside');assert.equal(one.label,null);
  const serialized=JSON.stringify(one);for(const secret of [input.canonical,'PRIVATE_NAME','SYNTHETIC_PERSON','SYNTHETIC_PRIVATE_ERROR',context.diagnostics.key])assert.ok(!serialized.includes(secret),'raw diagnostic value must not escape');
  const describe=p=>first.describe({...input,lexical:p,canonical:p,stack:''});
  assert.equal(describe('/proc/self/cgroup').label,'telemetry-container-probe:cgroup');
  assert.equal(describe('/proc/self/cgroup-neighbor').label,null);
  assert.equal(describe('/reviewed/project/package.json').label,'original-project-metadata:package.json');
  for(const p of ['/other/package.json','/reviewed/project/nested/package.json','/reviewed/project/package.json.backup'])assert.equal(describe(p).label,null);
  assert.equal(describe('/reviewed/project/src/lib/public.ts').label,'copied-source:src/lib/public.ts');
  assert.equal(describe('/reviewed/project/src/lib/other.ts').knownCopy,false);
  const bff=describe('/reviewed/project/src/app/api/private/[...path]/route.ts');assert.equal(bff.label,'public-bff-private-route');assert.equal(bff.knownCopy,true);assert.equal(bff.privateNameMatch,true);
  assert.equal(describe('/reviewed/project/src/secrets/not-public.ts').label,null);
  const alias=first.describe({...input,lexical:'/synthetic-alias',canonical:input.canonical});assert.notEqual(alias.lexicalId,alias.targetId);
  const budget=createDiagnostics(context,{maxEvents:1});budget.record(input);budget.record(input);assert.equal(budget.snapshot()[0].count,2);assert.throws(()=>budget.record({...input,canonical:'/different-private-target'}),/event budget/);
  assert.throws(()=>first.describe({...input,canonical:'x'.repeat(4097)}),/normalization/);
  assert.throws(()=>first.describe({...input,stack:new Error('SYNTHETIC_PRIVATE_ERROR')}),/normalization/);
  assert.equal(calls,0);
 }finally{for(const [name,original] of originals)fs[name]=original;}
});
test('installed deny keeps failure accounting and sanitized IDs separate from policy and native scope',()=>{
 const guard=require('../../scripts/safe-checks-guard.cjs'),cap=JSON.parse(fs.readFileSync(process.env.ST001_SAFE_CAP,'utf8'));
 assert.equal(fs.statSync(process.env.ST001_SAFE_CAP).mode&0o777,0o600);
 const target='/SYNTHETIC_PERSON/credentials/PRIVATE_TOKEN.pem',before=guard.observation();
 guard.expected(()=>fs.readFileSync(target));
 const after=guard.observation();assert.equal(after.rawDispatches,before.rawDispatches);assert.equal(after.deniedTotal,before.deniedTotal+1);assert.equal(after.expectedNegatives,before.expectedNegatives+1);assert.equal(after.violations.length,0);assert.equal(after.native,'not-observed');
 assert.ok(after.diagnostics.some(e=>e.run===cap.diagnostics.run&&e.privateNameMatch&&e.count>0));
 const serialized=JSON.stringify(after);for(const secret of [cap.diagnostics.key,target,'PRIVATE_TOKEN','SYNTHETIC_PERSON'])assert.ok(!serialized.includes(secret),'observation must not contain private value');
 for(const name of fs.readdirSync(process.cwd()).filter(n=>/^\.snapshot-ledger-\d+-[a-f0-9]{16}\.jsonl$/.test(n))){const journal=fs.readFileSync(path.join(process.cwd(),name),'utf8');for(const secret of [cap.diagnostics.key,target,'PRIVATE_TOKEN'])assert.ok(!journal.includes(secret),'journal must not contain private value');}
});
test('diagnostic aggregation preserves partial workers and bounded-record errors propagate',async()=>{
 const {createDiagnostics,journalLine}=require('../../scripts/safe-checks-guard.cjs');
 const {aggregateDiagnostics,reportObservations}=await import('../../scripts/check-local-ports.mjs');
 const context=syntheticDiagnosticContext(),d=createDiagnostics(context),event=d.record({lexical:'/synthetic-hidden',canonical:'/synthetic-hidden',api:'readFile',stack:''});
 const records=[{diagnostics:[{...event,count:1}]},{diagnostics:[{...event,count:2}]}];
 const result=aggregateDiagnostics(records,context.diagnostics.run,new Set());assert.equal(result.length,1);assert.equal(result[0].count,3);assert.equal(result[0].workers,2);
 assert.throws(()=>aggregateDiagnostics([{diagnostics:Array(257).fill({...event,count:1})}],context.diagnostics.run,new Set()),/budget/);
 assert.throws(()=>aggregateDiagnostics([{diagnostics:[{...event,count:1,label:'PRIVATE_NAME'}]}],context.diagnostics.run,new Set()),/invalid/);
 assert.throws(()=>journalLine('denied',{safe:true},0,4),/journal limit/);assert.throws(()=>journalLine('PRIVATE_ERROR',{safe:true},0),/configuration/);
 const folder=fs.mkdtempSync(path.join(os.tmpdir(),'diagnostic-journal-')),log=console.log;console.log=()=>{};
 try{
  const row={scope:'instrumented-js-fs-consumer-dispatch-only',rawOriginalDispatches:0,rawOriginalDenied:0,deniedTotal:0,expectedNegatives:0,diagnosticFailures:0,violations:[],diagnostics:[{...event,count:1}],snapshot:{hits:{readFile:0,readFileSync:0,promisesReadFile:0}}};
  fs.writeFileSync(path.join(folder,'.snapshot-ledger-1-1111111111111111.jsonl'),journalLine('exit',row,0));
  fs.writeFileSync(path.join(folder,'.snapshot-ledger-2-2222222222222222.jsonl'),journalLine('metadata-hit',row,0));
  const totals=reportObservations(folder,context.diagnostics);assert.equal(totals.exitRecords,1);assert.equal(totals.partialWorkers,1);assert.equal(totals.distinctTargets,1);
  fs.writeFileSync(path.join(folder,'.snapshot-ledger-1-1111111111111111.jsonl'),journalLine('exit',{...row,diagnosticFailures:1},0));
  assert.throws(()=>reportObservations(folder,context.diagnostics),/unexpected denial/);
 }finally{console.log=log;fs.rmSync(folder,{recursive:true});}
});

test('relocation copy inputs use only the exact reviewed source-to-target mapping',async()=>{
 const {relocationSources,relocatedSource}=await import('../../scripts/check-local-ports.mjs');
 assert.equal(Object.keys(relocationSources).length,37);
 assert.equal(relocatedSource('src/api/backend.ts'),'src/shared/api/backend.ts');
 assert.equal(relocatedSource('src/types/archive.ts'),'src/shared/contracts/report.ts');
 assert.equal(relocatedSource('src/components/ui/app-shell.tsx'),'src/shared/ui/app-shell.tsx');
 for(const name of ['src/api/backend.ts.backup','src/api/other.ts','src/keys/backend.ts','__proto__'])assert.equal(relocatedSource(name),name);
 assert.equal(Object.isFrozen(relocationSources),true);
 for(const target of Object.values(relocationSources).filter(p=>/\.(ts|tsx)$/.test(p)))assert.equal(sourceAllowed(target),true);
});
