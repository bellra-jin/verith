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
test('CF009 exact demo flag accepts only absent or string true/false without coercion or value exposure',()=>{
 const {validateDemoFlag}=require('../../scripts/safe-checks-guard.cjs');
 for(const value of [undefined,'true','false'])assert.equal(validateDemoFlag(value),value);
 const canary='CF009-SYNTHETIC-VALUE-DO-NOT-EXPOSE';
 const malformed=['',' ','TRUE','False',' true','false ','1',canary,null,true,false,0,1,{},[],new String('true'),Symbol(canary),1n,()=>canary,{toString(){throw Error(canary);}}];
 for(const value of malformed)assert.throws(()=>validateDemoFlag(value),error=>error.message==='SAFE_CHECK_DENIED: demo flag'&&!String(error).includes(canary));
});
test('CF009 actual preload block preserves the validated flag and removes secret/unknown lookalikes in a limited VM',()=>{
 const {validateDemoFlag}=require('../../scripts/safe-checks-guard.cjs');
 const source=fs.readFileSync(path.join(process.cwd(),'scripts/safe-checks-guard.cjs'),'utf8');
 const parsed=ts.createSourceFile('safe-checks-guard.cjs',source,ts.ScriptTarget.Latest,true,ts.ScriptKind.JS);
 const blocks=parsed.statements.filter(node=>ts.isIfStatement(node)&&node.expression.getText(parsed)==='process.env.ST001_SAFE_CAP');assert.equal(blocks.length,1);
 const block=blocks[0].getText(parsed);
 function preload(value){
  const env={ST001_SAFE_CAP:'synthetic-cap.json',NODE_OPTIONS:'--require=/owned/safe-checks-guard.cjs',OPENSSL_CONF:'/dev/null',GOOGLE_CLIENT_SECRET:'CF009-SECRET-CANARY',UNREVIEWED_ENV:'synthetic',FLOW_SYNTHETIC_DEMO_ENABLED_LOOKALIKE:'true'};
  if(value!==undefined)env.FLOW_SYNTHETIC_DEMO_ENABLED=value;
  let reads=0,installs=0;
  const context={process:{env},validateDemoFlag,installed:undefined,fs:{readFileSync(name,encoding){assert.equal(name,'synthetic-cap.json');assert.equal(encoding,'utf8');reads++;return '{}';}},install(cap){assert.equal(JSON.stringify(cap),'{}');installs++;return 'synthetic-install';}};
  return {env,run(){vm.runInNewContext(block,context,{timeout:100});},counts:()=>({reads,installs})};
 }
 for(const value of [undefined,'true','false']){
  const p=preload(value);p.run();assert.deepEqual(p.counts(),{reads:1,installs:1});
  assert.equal(Object.hasOwn(p.env,'FLOW_SYNTHETIC_DEMO_ENABLED'),value!==undefined);assert.equal(p.env.FLOW_SYNTHETIC_DEMO_ENABLED,value);
  assert.deepEqual(Object.keys(p.env).sort(),['ST001_SAFE_CAP','NODE_OPTIONS','OPENSSL_CONF',...(value===undefined?[]:['FLOW_SYNTHETIC_DEMO_ENABLED'])].sort());
  assert.equal(p.env.OPENSSL_CONF,'/dev/null');assert.equal(p.env.NODE_OPTIONS,'--require=/owned/safe-checks-guard.cjs');
 }
 for(const value of ['',' TRUE','1','CF009-SECRET-CANARY',null,false,1,{}]){
  const p=preload(value);assert.throws(()=>p.run(),error=>error.message==='SAFE_CHECK_DENIED: demo flag');assert.deepEqual(p.counts(),{reads:0,installs:0});
 }
});
test('CF009 actual fork plan keeps parent flag and rejects child injection/overrides while other protections stay pinned',()=>{
 const {forkPlan}=require('../../scripts/safe-checks-guard.cjs');
 const target=fs.realpathSync(path.join(process.cwd(),'node_modules/next/dist/compiled/jest-worker/processChild.js'));
 const base={root:process.cwd(),dependency:path.join(process.cwd(),'node_modules'),guard:path.join(process.cwd(),'scripts/safe-checks-guard.cjs')};
 const flag='FLOW_SYNTHETIC_DEMO_ENABLED';
 function plan(parent,child,includeChild=false){
  const environment={LANG:'en_US.UTF-8',ST001_SAFE_CAP:process.env.ST001_SAFE_CAP,GOOGLE_CLIENT_SECRET:'CF009-SECRET-CANARY',FLOW_SYNTHETIC_DEMO_ENABLED_LOOKALIKE:'true'};
  if(parent!==undefined)environment[flag]=parent;
  const env={ST001_SAFE_CAP:process.env.ST001_SAFE_CAP,JEST_WORKER_ID:'1',IS_NEXT_WORKER:'true',GOOGLE_CLIENT_SECRET:'CF009-SECRET-CANARY',UNREVIEWED_ENV:'synthetic',FLOW_SYNTHETIC_DEMO_ENABLED_LOOKALIKE:'true',NODE_OPTIONS:'--require=/synthetic/unapproved.cjs'};
  if(includeChild)env[flag]=child;
  return forkPlan(target,[],{cwd:base.root,env,execArgv:[],silent:true},{...base,environment});
 }
 const baseline=plan(undefined).options.env;
 for(const parent of [undefined,'true','false'])for(const includeChild of [false,true]){
  const p=plan(parent,parent,includeChild);assert.equal(p.options.env[flag],parent);assert.equal(Object.hasOwn(p.options.env,flag),parent!==undefined);
  const other={...p.options.env};delete other[flag];assert.deepEqual(other,baseline);
  for(const key of ['GOOGLE_CLIENT_SECRET','UNREVIEWED_ENV','FLOW_SYNTHETIC_DEMO_ENABLED_LOOKALIKE'])assert.equal(Object.hasOwn(p.options.env,key),false);
  assert.equal(p.options.env.NODE_OPTIONS,'--require='+base.guard);assert.equal(p.options.env.OPENSSL_CONF,'/dev/null');assert.equal(p.options.env.ST001_SAFE_CAP,process.env.ST001_SAFE_CAP);
  assert.deepEqual(p.options.stdio,['pipe','pipe','pipe','ipc']);assert.equal(p.options.detached,false);assert.equal(p.options.cwd,base.root);assert.equal(p.options.execPath,process.execPath);assert.deepEqual(p.options.execArgv,[]);
 }
 for(const parent of [undefined,'true','false'])for(const child of [undefined,'true','false','',' TRUE','1','CF009-SECRET-CANARY',null,false,1,{}]){
  if(child===parent)continue;
  assert.throws(()=>plan(parent,child,true),error=>error.message==='SAFE_CHECK_DENIED: demo flag');
 }
 for(const parent of ['',' TRUE','1','CF009-SECRET-CANARY',null,false,1,{}])assert.throws(()=>plan(parent),error=>error.message==='SAFE_CHECK_DENIED: demo flag');
});
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

test('CF019 exact focused sources and five production React inputs retain unit capability and original guard',async()=>{
 const entry=await import('../../scripts/check-local-ports.mjs');
 assert.deepEqual(entry.flowReviewUnit,['unit/flow/report-display.test.mjs','unit/flow/report-deletion.test.mjs','tooling/safe-checks.test.mjs']);
 assert.deepEqual(entry.reactProductionFiles,['react/cjs/react.production.js','react/cjs/react-jsx-runtime.production.js','react-dom/cjs/react-dom.production.js','react-dom/cjs/react-dom-client.production.js','scheduler/cjs/scheduler.production.js']);
 for(const name of entry.flowReviewExact){assert.equal(sourceAllowed(name),true);assert.equal(sourceAllowed(name+'.adjacent'),false);}
 const fixture=fs.readFileSync('tests/integration/flow/report-browser-fixture.mjs','utf8');
 assert.match(fixture,/cap.workload!=='unit'/);assert.match(fixture,/Content-Security-Policy/);assert.match(fixture,/finally/);
 assert.doesNotMatch(fixture,/from ['"](?:playwright|puppeteer)|child_process|https:\/\//);
 const tree=ts.createSourceFile('report-browser-fixture.mjs',fixture,ts.ScriptTarget.Latest,true,ts.ScriptKind.JS);
 assert.equal(tree.parseDiagnostics.length,0);
 const declarations=tree.statements.filter(ts.isVariableStatement).flatMap(s=>[...s.declarationList.declarations]);
 const bundle=declarations.find(n=>n.name.getText(tree)==='bundle').initializer;
 assert.ok(ts.isTemplateExpression(bundle));
 const syntax=bundle.head.text+bundle.templateSpans.map(span=>{
  const text=span.expression.getText(tree);
  return (text.startsWith('Object.entries(modules)')?'':text.includes('JSON.stringify(payload')?'{}':'"synthetic"')+span.literal.text;
 }).join('');
 assert.equal(ts.createSourceFile('fixture-bundle.js',syntax,ts.ScriptTarget.Latest,true,ts.ScriptKind.JS).parseDiagnostics.length,0);
 for(const phrase of ['authStatus','reportStatus','16000','removed.has','표시 '+"'"+'+name'])assert.ok(fixture.includes(phrase));
 // Execute only the fixture's fixed control function in a VM, never React/server.
 const generated=ts.createSourceFile('fixture-bundle.js',syntax,ts.ScriptTarget.Latest,true,ts.ScriptKind.JS);
 const controls=[];function visit(node){if(ts.isFunctionDeclaration(node)&&node.name?.text==='control')controls.push(node);ts.forEachChild(node,visit);}visit(generated);assert.equal(controls.length,1);
 const code=controls[0].getText(generated)+';control;';
 const applied={updated:true,account:'B',status:403,authStatus:401,reportStatus:404,delay:16000};
 for(const kind of ['success','http','malformed','transport']){
  const states=[],lock={current:false};let calls=0;
  const fetch=async()=>{calls++;if(kind==='transport')throw Error('synthetic raw error must not leak');return {ok:kind!=='http',json:async()=>kind==='malformed'?{updated:true}:applied};};
  const control=vm.runInNewContext(code,{controlLock:lock,setControlState:s=>states.push(s),fetch,AbortSignal},{timeout:100});
  await control({status:403});assert.equal(states[0].phase,'pending');assert.equal(calls,1);
  assert.equal(states.at(-1).phase,kind==='success'?'complete':'error');
  if(kind==='success'){assert.ok(states.at(-1).text.includes('적용 완료'));for(const [key,value] of Object.entries(applied).filter(([key])=>key!=='updated'))assert.ok(states.at(-1).text.includes(JSON.stringify(key)+':'+JSON.stringify(value)));assert.equal(lock.current,false);}
  else{assert.equal(states.at(-1).text,'합성 fixture 제어 오류 · 다음 클릭을 중단하고 새로고침하세요');await control({status:204});assert.equal(calls,1);assert.equal(lock.current,true);}
 }
 assert.match(fixture,/fieldset.*disabled:controlState.phase/);assert.match(fixture,/inert:controlState.phase/);

});


test('CF019 readiness preserves an early worker failure and keeps fixed proof/deadline checks',async()=>{
 const {browserReadiness}=await import('../../scripts/check-local-ports.mjs');
 let waits=0,reads=0;const failure=Error('check child failed 7: SYNTHETIC-WORKER-STDERR');
 await assert.rejects(browserReadiness(Promise.reject(failure),()=>{reads++;return null;},()=>{waits++;return new Promise(()=>{});}),error=>error===failure);
 assert.equal(reads,1);assert.equal(waits,1);
 await assert.rejects(browserReadiness(Promise.resolve('SYNTHETIC-EARLY-EXIT'),()=>null,async()=>{}),/worker exited before readiness: SYNTHETIC-EARLY-EXIT/);
 const running=new Promise(()=>{});waits=0;
 const proof={nonce:'synthetic',pid:123,cwd:'/owned',port:1234};
 assert.equal(await browserReadiness(running,()=>waits===2?proof:null,async()=>{waits++;}),proof);assert.equal(waits,2);
 waits=0;await assert.rejects(browserReadiness(running,()=>null,async()=>{waits++;}),/readiness timeout/);assert.equal(waits,100);
 const source=fs.readFileSync('scripts/check-local-ports.mjs','utf8');
 for(const check of ['proof.nonce!==owned.nonce','proof.cwd!==root','proof.port!==cap.ports[0]','child.pid===proof.pid&&child.st001OwnedRoot===root',"listener.includes('p'+proof.pid)","cwd.includes('n'+root)"])assert.ok(source.includes(check));
 assert.doesNotMatch(source,/task\.catch\(\(\)=>\{\}\)/);
});


test('CF019 command failure keeps stderr visible when the exit snapshot is long',async()=>{
 const {command}=await import('../../scripts/check-local-ports.mjs');const {EventEmitter}=await import('node:events');
 const child=Object.assign(new EventEmitter(),{pid:123,exitCode:7,signalCode:null,stdout:new EventEmitter(),stderr:new EventEmitter()});const children=new Set();let retired=0;
 await assert.rejects(command(['synthetic-only'],{root:process.cwd(),env:{},children,launch:()=>child,wait:async()=>{child.stderr.emit('data','SYNTHETIC-ACTUAL-WORKER-FAILURE\n');child.stdout.emit('data','ST001_SNAPSHOT '+JSON.stringify({synthetic:'x'.repeat(6000)})+'\n');},retire:async()=>{retired++;}}),error=>error.message==='check child failed 7: SYNTHETIC-ACTUAL-WORKER-FAILURE\n');
 assert.equal(retired,1);assert.equal(children.size,0);
});


test('CF019 Seatbelt rules use only the reserved localhost TCP ports, never wildcard or IP host syntax',async()=>{
 const {loopbackRules}=await import('../../scripts/check-local-ports.mjs');
 assert.deepEqual(loopbackRules([]),[]);
 assert.deepEqual(loopbackRules([3200,8200]),['(allow network-inbound (local tcp "localhost:3200"))','(allow network-outbound (remote tcp "localhost:3200"))','(allow network-inbound (local tcp "localhost:8200"))','(allow network-outbound (remote tcp "localhost:8200"))']);
 for(const ports of [[0],[65536],[-1],[1.5],['3200'],['*'],[3200,3200],[1,2,3],null])assert.throws(()=>loopbackRules(ports),/invalid exact loopback ports/);
 for(const line of loopbackRules([1,65535]))assert.doesNotMatch(line,/\*|127\.0\.0\.1|::1|udp/);
 const guard=fs.readFileSync('scripts/safe-checks-guard.cjs','utf8');
 assert.ok(guard.includes("['127.0.0.1','::1','localhost'].includes(host)"));assert.ok(guard.includes('cap.ports.includes(Number(port))'));
});

test('CF019 owned stop precedes command settlement and package postcheck; cleanup failures remain failures',async()=>{
 const {stopAndSettleBrowserTask}=await import('../../scripts/check-local-ports.mjs');
 for(const fail of [false,true]){
  const events=[];let finish;const commandFailure=Error('synthetic command failure');
  const task=new Promise(resolve=>{finish=resolve;}).then(()=>{events.push('package-postcheck');if(fail)throw commandFailure;});
  const result=await stopAndSettleBrowserTask(task,async()=>{events.push('owned-stop');finish();});events.push('root-may-clean');
  assert.deepEqual(events,['owned-stop','package-postcheck','root-may-clean']);
  assert.equal(result.status,fail?'rejected':'fulfilled');if(fail)assert.equal(result.error,commandFailure);
 }
 let finished=false;const cleanupFailure=Error('synthetic owned stop failure');
 await assert.rejects(stopAndSettleBrowserTask(Promise.resolve().then(()=>{finished=true;}),async()=>{throw cleanupFailure;}),error=>error===cleanupFailure);
 assert.equal(finished,true);
});


test('CF020 exact planning sources/modes reuse the existing protected worker and production inputs',async()=>{
 const c=await import('../../scripts/check-local-ports.mjs');
 assert.deepEqual(c.supervisorUnit,['unit/supervisor/query-plan.test.mjs','unit/flow/analysis-request.test.mjs','unit/bff/session-proxy.test.mjs','unit/config/ports.test.mjs','tooling/safe-checks.test.mjs']);
 for(const p of c.supervisorExact){assert.equal(c.sourceAllowed(p),true);assert.ok(c.readSource(process.cwd(),p).length);assert.equal(c.sourceAllowed(p+'.adjacent'),false);}
 for(const mode of ['supervisor-unit','supervisor-type','supervisor-lint','supervisor-browser'])assert.ok(c.modes.includes(mode));
 const source=fs.readFileSync('scripts/check-local-ports.mjs','utf8');assert.match(source,/cap.cf020Planning=supervisorBrowser/);assert.match(source,/workload:selected.length===1/);
 assert.equal(c.reactProductionFiles.length,5);
});

test('CF022 core modes keep fixed unit/source selection, existing guard and same production fixture inputs',async()=>{
 const c=await import('../../scripts/check-local-ports.mjs');assert.deepEqual(c.coreUnit,['unit/supervisor/core.test.mjs','unit/bff/session-proxy.test.mjs','unit/config/ports.test.mjs','tooling/safe-checks.test.mjs']);
 assert.ok(c.modes.includes('core-type')&&c.modes.includes('core-browser'));assert.equal(c.reactProductionFiles.length,5);
 const source=fs.readFileSync('scripts/check-local-ports.mjs','utf8');assert.ok(source.includes('cap.cf022Core=coreBrowser'));assert.ok(source.includes("coreOnly?['-p','tsconfig.cf022.json']"));
});

test('CF022 split metadata retains pinned code provenance and strict worker snapshot',async()=>{
 const {packageRecord,manifestIdentity,sourceProvenance,recheckProvenance,checkedCommand,diagnosticCopySources,metadataRootFor}=await import('../../scripts/check-local-ports.mjs');
 const guard=require('../../scripts/safe-checks-guard.cjs');
 const packageBytes=fs.readFileSync(path.join(process.cwd(),'package.json'));
 const lockBytes=fs.readFileSync(path.join(process.cwd(),'package-lock.json'));
 const {createHash}=await import('node:crypto');
 const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
 async function fixture(change=()=>{},failure=false){
  const base=fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(),'cf022-provenance-')));
  const codeRoot=path.join(base,'code'),metadataRoot=path.join(base,'metadata'),dependency=path.join(metadataRoot,'node_modules'),root=path.join(base,'owned');
  for(const p of [codeRoot,dependency,root])fs.mkdirSync(p,{recursive:true});
  fs.symlinkSync(dependency,path.join(codeRoot,'node_modules'));
  const hashes={};
  for(const [relative,bytes] of [['package.json',packageBytes],['package-lock.json',lockBytes],['src/core.ts',Buffer.from('export const value=1;')],['tests/unit/fundamental/analysis-request.test.mjs',Buffer.from('// exact pre-existing fresh input')]]){
   for(const parent of [codeRoot,root]){const file=path.join(parent,relative);fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,bytes);}
   hashes[relative]=sha(bytes);
  }
  fs.writeFileSync(path.join(metadataRoot,'package.json'),packageBytes);
  fs.writeFileSync(path.join(root,'source-hashes.json'),JSON.stringify(hashes),{mode:0o600});
  const record=packageRecord(root,dependency,packageBytes,manifestIdentity(path.join(metadataRoot,'package.json')),metadataRoot);
  const provenance=sourceProvenance(root,dependency,record,hashes,codeRoot);
  let metadataOpens=0;
  const io={...fs,openSync(file,...args){if(file===record.literal){metadataOpens++;throw Error('original literal open');}return fs.openSync(file,...args);}};
  try{
   assert.deepEqual(guard.loadPackageSnapshot({root,dependency,packageSnapshot:record},io),packageBytes);assert.equal(metadataOpens,0);
   assert.deepEqual(diagnosticCopySources(codeRoot,metadataRoot,['src/core.ts']),[]);
   assert.deepEqual(diagnosticCopySources(codeRoot,codeRoot,['src/core.ts']),['src/core.ts']);
   assert.equal(provenance.codeRoot,codeRoot);assert.equal(record.sourceRoot,metadataRoot);
   assert.throws(()=>metadataRootFor(codeRoot,dependency),/unreviewed metadata root/);
   recheckProvenance(provenance,root,dependency,record);
   const state={codeRoot,metadataRoot,root,dependency,record};
   if(failure){
    let postchecked=0;const original=fs.openSync;
    fs.openSync=function(file,...args){if(file===path.join(codeRoot,'package-lock.json'))postchecked++;return original.call(this,file,...args);};
    try{await assert.rejects(checkedCommand({record,root,dependency,provenance,argv:[],env:{},timeout:1,children:new Set(),invoke:async()=>{throw Error('synthetic child failure');}}),/synthetic child failure/);assert.ok(postchecked>=2);}finally{fs.openSync=original;}
   }else change(state);
   if(change!==noop)assert.throws(()=>{guard.loadPackageSnapshot({root,dependency,packageSnapshot:record},io);recheckProvenance(provenance,root,dependency,record);});
  }finally{fs.rmSync(base,{recursive:true});}
 }
 function noop(){}
 await fixture(noop);await fixture(noop,true);
 for(const [which,relative] of [['codeRoot','package.json'],['codeRoot','package-lock.json'],['codeRoot','src/core.ts'],['metadataRoot','package.json'],['root','package.json'],['root','src/core.ts'],['root','source-hashes.json']])await fixture(state=>fs.appendFileSync(path.join(state[which],relative),' '));
 await fixture(({codeRoot,dependency})=>{fs.unlinkSync(path.join(codeRoot,'node_modules'));fs.mkdirSync(path.join(codeRoot,'node_modules'));assert.notEqual(fs.realpathSync(path.join(codeRoot,'node_modules')),dependency);});
 await fixture(({record,metadataRoot})=>{fs.unlinkSync(record.literal);fs.symlinkSync(path.join(metadataRoot,'node_modules'),record.literal);});
 await fixture(({record,metadataRoot})=>fs.linkSync(record.literal,path.join(metadataRoot,'second-link')));
 const cap=JSON.parse(fs.readFileSync(process.env.ST001_SAFE_CAP,'utf8'));
 assert.throws(()=>guard.loadPackageSnapshot({...cap,packageSnapshot:{...cap.packageSnapshot,extra:true}}),/SAFE_CHECK_DENIED/);
 const provenance=JSON.parse(fs.readFileSync(path.join(process.cwd(),'source-provenance.json'),'utf8'));
 for(const sourceRoot of new Set([provenance.codeRoot,cap.packageSnapshot.sourceRoot]))guard.expected(()=>fs.readFileSync(path.join(sourceRoot,'src/adjacent.ts')));
 const diagnostics=guard.createDiagnostics({root:process.cwd(),dependency:cap.dependency,sourceRoot:cap.packageSnapshot.sourceRoot,runtime:cap.runtime,workerRole:'entry-worker',workload:'unit',diagnostics:{key:'a'.repeat(64),run:'b'.repeat(24),copySources:[]}});
 const observation=diagnostics.describe({lexical:path.join(cap.packageSnapshot.sourceRoot,'src/core.ts'),canonical:path.join(cap.packageSnapshot.sourceRoot,'src/core.ts')});
 assert.equal(observation.knownCopy,false);
});

test('CF023 controller/resource selection adds no adjacent input and leaves the worker guard unchanged',async()=>{
 const c=await import('../../scripts/check-local-ports.mjs');
 for(const source of ['src/features/supervisor/components/supervisor-session.tsx','tests/fixtures/cf023-supervisor-meaning.json']){
  assert.ok(c.coreExact.includes(source));assert.equal(c.sourceAllowed(source),true);assert.equal(c.sourceAllowed(source+'.adjacent'),false);assert.ok(c.readSource(process.cwd(),source).length);
 }
 const {createHash}=await import('node:crypto');
 assert.equal(createHash('sha256').update(fs.readFileSync('scripts/safe-checks-guard.cjs')).digest('hex'),'3a9cb45bc865d560612ccd5876f060c69aa0abe5ff635576888781d9efe7d3ee');
 const fixture=fs.readFileSync('tests/integration/supervisor/chat-browser-fixture.mjs','utf8');
 assert.match(fixture,/SupervisorSession/);assert.match(fixture,/cf019-ready.json/);assert.match(fixture,/server.closeAllConnections/);assert.match(fixture,/590000/);assert.doesNotMatch(fixture,/function FakeApp|verified:true|next\/navigation/);
 assert.equal(c.reactProductionFiles.length,5);
});

test('CF025 one raw URL validator rejects normalization/query bypasses and canonicalizes only UUIDs',async()=>{
 const {validateFixtureTarget:parse}=await import('../helpers/supervisor-fixture.mjs');
 const id='AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA';
 assert.deepEqual(parse('/research'),{status:200,kind:'research',id:null});assert.equal(parse('/research?supervisor_id='+id).id,id.toLowerCase());
 for(const value of ['/research?','/research?supervisor_id=','/research?supervisor_id=no','/research?supervisor_id='+id+'&supervisor_id='+id,'/research?unknown=x','/research?analysis_id='+id,'/research?supervisor_id='+id+'&','/research??supervisor_id='+id,'//research','https://example.invalid/research','/research#x','/research\\x','/research\n','/research/../research','/%72esearch','/research?%73upervisor_id='+id,'/research?'+('한'.repeat(1000))])assert.equal(parse(value).status,422);
 assert.equal(parse('/').status,404);assert.equal(parse('/other').status,404);assert.equal(parse('/bundle.js?x=1').status,422);
});

test('CF025 actual route adapter preserves initial/reloaded IDs, back navigation and listener cleanup',async()=>{
 const {fixtureAdapter}=await import('../helpers/supervisor-fixture.mjs');
 const id='AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA',ids=[],listeners=new Map(),calls=[];let invalid=0,outside=0;
 const location={pathname:'/research',search:'?supervisor_id='+id,hash:''};
 const history=Object.fromEntries(['pushState','replaceState'].map(name=>[name,(_state,_title,href)=>{calls.push([name,href]);const u=new URL(href,'http://127.0.0.1:1234');Object.assign(location,{pathname:u.pathname,search:u.search,hash:u.hash});}]));
 const adapter=fixtureAdapter({origin:'http://127.0.0.1:1234',location,history,events:{addEventListener:(k,v)=>listeners.set(k,v),removeEventListener:(k,v)=>{assert.equal(listeners.get(k),v);listeners.delete(k);}},onChange:id=>ids.push(id),onInvalid:()=>invalid++,onOutside:()=>outside++});
 assert.equal(adapter.initial.id,id.toLowerCase());const cleanup=adapter.listen();assert.equal(calls.length,0);
 adapter.navigate('/research',true);assert.equal(ids.at(-1),null);adapter.navigate('http://127.0.0.1:1234/research?supervisor_id='+id);assert.equal(ids.at(-1),id.toLowerCase());
 Object.assign(location,{search:'',hash:''});listeners.get('popstate')();assert.equal(ids.at(-1),null);
 location.search='?analysis_id='+id;listeners.get('popstate')();assert.equal(invalid,1);
 adapter.navigate('https://example.invalid/research');adapter.navigate('/research?supervisor_id=x');assert.equal(invalid,3);
 adapter.navigate('/reports/flow/'+id);assert.equal(outside,1);assert.equal(calls.length,2);cleanup();assert.equal(listeners.size,0);
});

test('CF025 terminal exact lexical body closes duplicate/extra keys and never trusts client counters',async()=>{
 const {terminalAction}=await import('../helpers/supervisor-fixture.mjs');
 for(const action of ['complete','cancel'])assert.equal(terminalAction(' { "action" : "'+action+'" } '),action);
 for(const value of ['null','[]','{}','{"action":"complete","action":"cancel"}','{"action":"complete","counts":{}}','{"action":"other"}','{"action":true}','{"action":"complete"} trailing'])assert.throws(()=>terminalAction(value),/terminal body invalid/);
});

test('CF025 actual lifecycle freezes after the first transition, drains before receipt/ACK/close',async()=>{
 const {createFixtureTerminal}=await import('../helpers/supervisor-fixture.mjs');
 for(const action of ['complete','cancel','timed_out','failed']){
  const events=[];let release;const terminal=createFixtureTerminal({stopWork(){events.push('fenced');},drain:()=>new Promise(resolve=>{release=()=>{events.push('drained');resolve();};}),writeReceipt:async value=>{events.push('receipt');return value;},ack:async()=>events.push('ack'),close:async()=>events.push('close')});
  let count=0;const delayed=()=>{if(terminal.open())count++;};delayed();const done=terminal.finish(action);delayed();
  assert.equal(count,1);assert.equal(terminal.phase,'closing');await assert.rejects(terminal.finish(action==='complete'?'cancel':'complete'),/conflict/);release();
  const receipt=await done;assert.equal(receipt.state,{complete:'completed',cancel:'cancelled',timed_out:'timed_out',failed:'failed'}[action]);assert.deepEqual(events,['fenced','drained','receipt','ack','close']);assert.equal(terminal.open(),false);await assert.rejects(terminal.finish(action),/conflict/);
 }
});

test('CF025 drain/receipt/ACK/close failures never become completed; cleanup failure propagates',async()=>{
 const {createFixtureTerminal}=await import('../helpers/supervisor-fixture.mjs');
 for(const fail of ['drain','receipt','ack','close']){
  const events=[];const invoke=async name=>{events.push(name);if(name===fail)throw Error('synthetic '+fail);};
  const terminal=createFixtureTerminal({stopWork(){},drain:()=>invoke('drain'),writeReceipt:()=>invoke('receipt'),ack:()=>invoke('ack'),close:()=>invoke('close')});
  await assert.rejects(terminal.finish('complete'),new RegExp('synthetic '+fail));assert.equal(terminal.phase,'failed');assert.ok(events.includes('close'));
  if(fail==='drain')assert.equal(events.includes('receipt'),false);
 }
});

function cf025Receipt(action='complete'){
 return {schema:'cf025.terminal.v1',nonce:'synthetic',pid:123,cwd:'/owned',port:1234,action,state:action==='complete'?'completed':'cancelled',counts:{sessionGET:1,preparePOST:1,prepareGET:0,prepareDELETE:0,confirmPOST:1,outcomeGET:1,model:0,provider:0},browser:Object.fromEntries(['react_mount','interaction','storage_navigation','visual_1440','visual_390','focus'].map(k=>[k,'not_executed']))};
}
test('CF025 parent actual callbacks require receipt plus both settlements and postcheck; unknown ACK stays unknown',async()=>{
 const {collectFixtureTerminal,validateTerminalReceipt}=await import('../helpers/supervisor-fixture.mjs');
 for(const action of ['complete','cancel'])for(const ack of ['received','unknown']){
  const receipt=cf025Receipt(action),events=[];
  const result=await collectFixtureTerminal({probe:Promise.resolve({action,ack,counts:receipt.counts,http:{reload:'passed'}}),child:Promise.resolve('exit0'),proof:receipt,readReceipt:async()=>{events.push('receipt');return receipt;},postcheck:async()=>events.push('postcheck')});
  assert.equal(result.ack,ack);assert.equal(result.receipt.state,receipt.state);assert.deepEqual(events,['postcheck','receipt']);assert.equal(result.browser.react_mount,'not_executed');
 }
 for(const mutation of [r=>r.pid++,r=>r.nonce='wrong',r=>r.counts.provider++,r=>r.browser.interaction='passed',r=>r.state='cancelled',r=>r.extra=true]){const receipt=cf025Receipt(),proof={...receipt};mutation(receipt);assert.throws(()=>validateTerminalReceipt(receipt,proof),/mismatch/);}
 const receipt=cf025Receipt(),base={probe:Promise.resolve({action:'complete',ack:'received',counts:receipt.counts,http:{}}),child:Promise.resolve(),proof:receipt,readReceipt:async()=>receipt,postcheck:async()=>{}};
 await assert.rejects(collectFixtureTerminal({...base,child:Promise.reject(Error('early child failure'))}),/child settlement/);
 await assert.rejects(collectFixtureTerminal({...base,probe:Promise.reject(Error('probe failure'))}),/probe failed/);
 await assert.rejects(collectFixtureTerminal({...base,postcheck:async()=>{throw Error('postcheck failure');}}),/postcheck failure/);
 await assert.rejects(collectFixtureTerminal({...base,readReceipt:async()=>{throw Error('receipt absent');}}),/receipt absent/);
});

test('CF025 parent reads only a new private regular terminal file; symlinks/hardlinks/mode/size fail',async()=>{
 const {readTerminal,fixtureSources}=await import('../../scripts/check-local-ports.mjs');
 const {createHash}=await import('node:crypto');
 assert.equal(createHash('sha256').update(fs.readFileSync('scripts/safe-checks-guard.cjs')).digest('hex'),'3a9cb45bc865d560612ccd5876f060c69aa0abe5ff635576888781d9efe7d3ee');
 assert.equal(fixtureSources.length,5);for(const source of fixtureSources)assert.equal(sourceAllowed(source),true);
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'cf025-receipt-')),file=path.join(root,'cf025-terminal.json'),value=cf025Receipt();
 try{
  fs.writeFileSync(file,JSON.stringify(value),{mode:0o600,flag:'wx'});assert.deepEqual(readTerminal(root),value);
  fs.chmodSync(file,0o644);assert.throws(()=>readTerminal(root),/identity/);fs.chmodSync(file,0o600);
  fs.linkSync(file,path.join(root,'second'));assert.throws(()=>readTerminal(root),/identity/);fs.unlinkSync(path.join(root,'second'));
  fs.renameSync(file,path.join(root,'saved'));fs.symlinkSync(path.join(root,'saved'),file);assert.throws(()=>readTerminal(root),/identity/);fs.unlinkSync(file);
  fs.writeFileSync(file,'x'.repeat(16385),{mode:0o600});assert.throws(()=>readTerminal(root),/identity/);
 }finally{fs.rmSync(root,{recursive:true});}
});

test('CF025 stopped signal only resumes after final terminal phase, never closing',async()=>{
 const {createFixtureTerminal}=await import('../helpers/supervisor-fixture.mjs');
 for(const action of ['complete','cancel']){
  let signal;const stopped=new Promise(resolve=>{signal=resolve;});const events=[];
  const terminal=createFixtureTerminal({stopWork(){},drain:async()=>{},writeReceipt:async v=>v,ack:async()=>{},close:async()=>{events.push('close');await Promise.resolve();},settled(){events.push(terminal.phase);signal();}});
  const task=terminal.finish(action);await stopped;
  assert.equal(terminal.phase,action==='complete'?'completed':'cancelled');assert.deepEqual(events,['close',terminal.phase]);await task;
 }
});

test('CF025 unknown ACK means absent response only; received HTTP/JSON/state errors remain failures',async()=>{
 const {terminalAcknowledgement,FixtureProtocolError}=await import('../helpers/supervisor-fixture.mjs');
 await assert.rejects(terminalAcknowledgement(async()=>{throw new FixtureProtocolError();},'complete'),/ACK invalid/);
 assert.equal((await terminalAcknowledgement(async()=>{throw Error('transport uncertain');},'complete')).ack,'unknown');
 for(const action of ['complete','cancel'])assert.equal((await terminalAcknowledgement(async()=>({status:200,json:()=>({state:action==='complete'?'completed':'cancelled'})}),action)).ack,'received');
 for(const response of [{status:409,json:()=>({state:'completed'})},{status:500,json:()=>({state:'completed'})},{status:200,json:()=>{throw Error('malformed');}},{status:200,json:()=>({state:'cancelled'})},{status:200,json:()=>({state:'completed',extra:true})}])await assert.rejects(terminalAcknowledgement(async()=>response,'complete'),/ACK invalid/);
});

test('CF025 actual fixture body receiver pauses oversize without destroying its response socket and bounds body wait',async()=>{
 const {EventEmitter}=await import('node:events');
 const source=fs.readFileSync('tests/integration/supervisor/chat-browser-fixture.mjs','utf8'),tree=ts.createSourceFile('fixture.mjs',source,ts.ScriptTarget.Latest,true,ts.ScriptKind.JS);
 const node=tree.statements.find(n=>ts.isFunctionDeclaration(n)&&n.name?.text==='readBody');assert.ok(node);
 for(const kind of ['valid','oversize','timeout','aborted']){
  const req=new EventEmitter();let paused=0,cleared=0,fire,delay;
  req.pause=()=>paused++;req.destroy=()=>{throw Error('must not destroy socket before fixed error response');};
  const read=vm.runInNewContext(node.getText(tree)+';readBody;',{Buffer,Promise,Date:{now:()=>0},expires:590000,setTimeout(fn,ms){fire=fn;delay=ms;return 1;},clearTimeout(){cleared++;}},{timeout:100});
  const task=read(req,1024);
  assert.equal(delay,5000);
  if(kind==='valid'){req.emit('data',Buffer.from('{"action":"complete"}'));req.emit('end');assert.equal(await task,'{"action":"complete"}');assert.equal(paused,0);}
  else{if(kind==='oversize')req.emit('data',Buffer.alloc(1025));else if(kind==='timeout')fire();else req.emit('aborted');await assert.rejects(task,/body invalid/);assert.equal(paused,1);}
  assert.equal(cleared,1);for(const event of ['data','end','error','aborted'])assert.equal(req.listenerCount(event),0);
 }
});

test('CF025 actual probe absolute deadline survives trickled response bytes, independent of inactivity timer',async()=>{
 const {EventEmitter}=await import('node:events');
 const source=fs.readFileSync('tests/integration/supervisor/chat-http-readiness.test.mjs','utf8'),tree=ts.createSourceFile('probe.mjs',source,ts.ScriptTarget.Latest,true,ts.ScriptKind.JS);
 const node=tree.statements.find(n=>ts.isFunctionDeclaration(n)&&n.name?.text==='request');assert.ok(node);
 let responseCallback,absolute,delay,inactivity,cleared=0;
 const req=new EventEmitter();req.end=()=>{};req.setTimeout=ms=>{inactivity=ms;};req.destroy=error=>{req.emit('error',error);req.emit('close');};
 const requests=new Set(),read=vm.runInNewContext(node.getText(tree)+';request;',{Buffer,Promise,Date:{now:()=>0},deadline:60000,origin:'http://127.0.0.1:1234',proof:{port:1234},requests,http:{request(options,callback){assert.equal(options.hostname,'127.0.0.1');assert.equal(options.port,1234);responseCallback=callback;return req;}},setTimeout(fn,ms){absolute=fn;delay=ms;return 1;},clearTimeout(){cleared++;}},{timeout:100});
 const task=read('/research');const res=new EventEmitter();res.statusCode=200;res.headers={};responseCallback(res);
 for(let n=0;n<5;n++)res.emit('data',Buffer.from('a'));
 assert.equal(delay,5000);assert.equal(inactivity,5000);absolute();await assert.rejects(task,/absolute request deadline/);assert.equal(cleared,1);assert.equal(requests.size,0);
});

test('CF025 actual probe received response cap/parser violations cannot be recovered as unknown terminal ACK',async()=>{
 const {EventEmitter}=await import('node:events');
 const {FixtureProtocolError,terminalAcknowledgement}=await import('../helpers/supervisor-fixture.mjs');
 const source=fs.readFileSync('tests/integration/supervisor/chat-http-readiness.test.mjs','utf8'),tree=ts.createSourceFile('probe.mjs',source,ts.ScriptTarget.Latest,true,ts.ScriptKind.JS);
 const node=tree.statements.find(n=>ts.isFunctionDeclaration(n)&&n.name?.text==='request');
 for(const kind of ['size','parser','incomplete']){
  let respond;const req=new EventEmitter();req.end=()=>{};req.setTimeout=()=>{};req.destroy=e=>{req.emit('error',e);req.emit('close');};
  const request=vm.runInNewContext(node.getText(tree)+';request;',{Buffer,Promise,Date:{now:()=>0},deadline:60000,origin:'http://127.0.0.1:1234',proof:{port:1234},requests:new Set(),FixtureProtocolError,http:{request(_options,callback){respond=callback;return req;}},setTimeout(){return 1;},clearTimeout(){}},{timeout:100});
  const job=terminalAcknowledgement(()=>request('/fixture-finish',{method:'POST',body:'{"action":"complete"}',limit:1}),'complete');
  if(kind==='size'){const res=new EventEmitter();res.statusCode=200;res.headers={};respond(res);res.emit('data',Buffer.from('xx'));}
  else if(kind==='parser')req.destroy(Object.assign(Error('synthetic parser failure'),{code:'HPE_INVALID_STATUS'}));
  else req.destroy(Object.assign(Error('incomplete response'),{code:'ECONNRESET'}));
  if(kind==='incomplete')assert.equal((await job).ack,'unknown');else await assert.rejects(job,/ACK invalid/);
 }
});

test('CF021 technical boundary mode selects only the pure preview test, tooling and typed chart inputs',async()=>{
 const caller=await import('../../scripts/check-local-ports.mjs');
 assert.deepEqual(caller.technicalBoundaryUnit,['unit/technical/boundary-preview.test.mjs','tooling/safe-checks.test.mjs']);
 assert.deepEqual(caller.technicalBoundaryType,['src/features/technical/lib/boundary-preview.ts','src/features/technical/model/types.ts']);
 assert.deepEqual(caller.technicalBoundaryExact,[...caller.technicalBoundaryType,...caller.technicalBoundaryUnit.map(p=>'tests/'+p),'src/features/technical/lib/chart.ts','tests/fixtures/cf021-technical-boundary.json']);
 for(const mode of ['technical-boundary-unit','technical-boundary-type','technical-boundary-lint'])assert.ok(caller.modes.includes(mode));
 for(const source of caller.technicalBoundaryExact)assert.equal(sourceAllowed(source),true);
 const text=fs.readFileSync('scripts/check-local-ports.mjs','utf8'),tree=ts.createSourceFile('caller.mjs',text,ts.ScriptTarget.Latest,true,ts.ScriptKind.JS);
 const execute=tree.statements.find(n=>ts.isFunctionDeclaration(n)&&n.name?.text==='execute');
 const declaration=execute.body.statements.find(n=>ts.isVariableStatement(n)&&n.declarationList.declarations.some(d=>d.name.getText(tree)==='technicalBoundaryOnly'));
 const selection=execute.body.statements.find(n=>ts.isIfStatement(n)&&n.expression.getText(tree)==='technicalBoundaryOnly');
 for(const [name,result] of [['unit','unit'],['type','type'],['lint','lint']]){
  const ctx={selected:['technical-boundary-'+name]};vm.runInNewContext(declaration.getText(tree)+'\n'+selection.getText(tree),ctx,{timeout:100});assert.deepEqual(Array.from(ctx.selected),[result]);
 }
 assert.match(text,/technicalBoundaryOnly\?technicalBoundaryUnit:coreOnly\?coreUnit/);
 assert.match(text,/technicalBoundaryOnly\?\['-p','tsconfig.cf021.json'\]/);
 assert.doesNotMatch(caller.technicalBoundaryExact.join('\n'),/components\/|app\/|\.env|boundary_runtime/);
});

test('CF021 exact Technical worktree alias preserves dependency identity and rejects sibling lookalikes',()=>{
 const source=fs.readFileSync('scripts/check-local-ports.mjs','utf8'),tree=ts.createSourceFile('caller.mjs',source,ts.ScriptTarget.Latest,true,ts.ScriptKind.JS);
 const vars=new Set(['reviewedWorkspace','reviewedCodeRoots','reviewedDependencyRoot']),functions=new Set(['trusted','metadataRootFor']);
 const selected=tree.statements.filter(n=>ts.isVariableStatement(n)&&n.declarationList.declarations.some(d=>vars.has(d.name.getText(tree)))||ts.isFunctionDeclaration(n)&&functions.has(n.name?.text));assert.equal(selected.length,5);
 const code=selected.map(n=>n.getText(tree).replace(/^export /,'')).join('\n')+';metadataRootFor;';
 const workspace='/synthetic/workspace',project=path.join(workspace,'verith-technical-boundary','frontend'),dependency=path.join(workspace,'verith','frontend','node_modules');
 function check(root,dep=dependency,{target=dep,uid=1234,mode=0o40755,canonical=root}={}){
  const paths=new Map([[root,canonical],[dep,dep],[path.join(root,'node_modules'),target],[path.dirname(dep),path.dirname(dep)]]);
  const fsMock={realpathSync(p){assert.ok(paths.has(p));return paths.get(p);},statSync(p){assert.ok([...paths.values()].includes(p));return {uid,mode};}};
  return vm.runInNewContext(code,{project,path,fs:fsMock,process:{getuid:()=>1234}},{timeout:100})(root,dep);
 }
 for(const sibling of ['verith-supervisor-core','verith-supervisor-verification','verith-supervisor-preparation-deadline','verith-technical-boundary','verith-technical-read-boundary','verith-technical-chart-display','verith-technical-chart-browser','verith-technical-owned-read'])assert.equal(check(path.join(workspace,sibling,'frontend')),path.dirname(dependency));
 for(const root of [path.join(workspace,'verith-technical-boundary-extra','frontend'),path.join(workspace,'prefix-verith-technical-boundary','frontend'),'/other/verith-technical-boundary/frontend'])assert.throws(()=>check(root),/unreviewed metadata root/);
 assert.throws(()=>check(project,'/other/dependency/node_modules'),/unreviewed metadata root/);
 assert.throws(()=>check(project,dependency,{target:'/other/node_modules'}),/code\/dependency identity mismatch/);
 assert.throws(()=>check(project,dependency,{canonical:'/other/code'}),/code\/dependency identity mismatch/);
 assert.throws(()=>check(project,dependency,{uid:9999}),/untrusted dependency metadata/);
 assert.throws(()=>check(project,dependency,{mode:0o40777}),/untrusted dependency metadata/);
});

test('CF031 read modes select exact pure decoder inputs and preserve CF021 selection',async()=>{
 const caller=await import('../../scripts/check-local-ports.mjs');
 assert.deepEqual(caller.technicalReadUnit,['unit/technical/boundary-read.test.mjs','tooling/safe-checks.test.mjs']);
 assert.deepEqual(caller.technicalReadType,['src/features/technical/lib/strict-boundary-read.ts','src/features/technical/lib/boundary-preview.ts','src/features/technical/model/types.ts']);
 assert.deepEqual(caller.technicalReadExact,[...caller.technicalReadType,...caller.technicalReadUnit.map(p=>'tests/'+p),'src/features/technical/lib/chart.ts','tests/fixtures/cf031-technical-boundary-read.json']);
 for(const name of caller.technicalReadExact)assert.equal(sourceAllowed(name),true);
 for(const name of ['tests/fixtures/cf031-technical-boundary-read.json.adjacent','tests/fixtures/cf031-other.json','tests/unit/technical/boundary-read.test.mjs.adjacent'])assert.equal(sourceAllowed(name),false);
 assert.deepEqual(caller.technicalBoundaryUnit,['unit/technical/boundary-preview.test.mjs','tooling/safe-checks.test.mjs']);
 const source=fs.readFileSync('scripts/check-local-ports.mjs','utf8'),tree=ts.createSourceFile('caller.mjs',source,ts.ScriptTarget.Latest,true,ts.ScriptKind.JS);
 const execute=tree.statements.find(n=>ts.isFunctionDeclaration(n)&&n.name?.text==='execute');
 const declaration=execute.body.statements.find(n=>ts.isVariableStatement(n)&&n.declarationList.declarations.some(d=>d.name.getText(tree)==='technicalReadOnly'));
 const selection=execute.body.statements.find(n=>ts.isIfStatement(n)&&n.expression.getText(tree)==='technicalReadOnly');
 for(const mode of ['unit','type','lint']){
  assert.ok(caller.modes.includes('technical-read-'+mode));
  const ctx={selected:['technical-read-'+mode]};vm.runInNewContext(declaration.getText(tree)+'\n'+selection.getText(tree),ctx,{timeout:100});assert.deepEqual(Array.from(ctx.selected),[mode]);
 }
 const bad={selected:['technical-read-extra']};vm.runInNewContext(declaration.getText(tree)+'\n'+selection.getText(tree),bad,{timeout:100});assert.equal(bad.technicalReadOnly,undefined);assert.deepEqual(bad.selected,['technical-read-extra']);
 assert.match(source,/technicalReadOnly\?technicalReadUnit:technicalBoundaryOnly\?technicalBoundaryUnit/);
 assert.match(source,/technicalReadOnly\?\['-p','tsconfig.cf031.json'\]/);
 assert.doesNotMatch(caller.technicalReadExact.join('\n'),/components\/|app\/|\.env|boundary_runtime/);
});

test('CF031 exact read worktree alias keeps negative provenance identity checks',()=>{
 const source=fs.readFileSync('scripts/check-local-ports.mjs','utf8'),tree=ts.createSourceFile('caller.mjs',source,ts.ScriptTarget.Latest,true,ts.ScriptKind.JS);
 const vars=new Set(['reviewedWorkspace','reviewedCodeRoots','reviewedDependencyRoot']),functions=new Set(['trusted','metadataRootFor']);
 const selected=tree.statements.filter(n=>ts.isVariableStatement(n)&&n.declarationList.declarations.some(d=>vars.has(d.name.getText(tree)))||ts.isFunctionDeclaration(n)&&functions.has(n.name?.text));assert.equal(selected.length,5);
 const code=selected.map(n=>n.getText(tree).replace(/^export /,'')).join('\n')+';metadataRootFor;';
 const workspace='/synthetic/workspace',project=path.join(workspace,'verith-technical-read-boundary','frontend'),dependency=path.join(workspace,'verith','frontend','node_modules');
 function check(root,dep=dependency,{target=dep,uid=1234,mode=0o40755,canonical=root}={}){
  const paths=new Map([[root,canonical],[dep,dep],[path.join(root,'node_modules'),target],[path.dirname(dep),path.dirname(dep)]]);
  const fsMock={realpathSync(p){assert.ok(paths.has(p));return paths.get(p);},statSync(p){assert.ok([...paths.values()].includes(p));return {uid,mode};}};
  return vm.runInNewContext(code,{project,path,fs:fsMock,process:{getuid:()=>1234}},{timeout:100})(root,dep);
 }
 assert.equal(check(project),path.dirname(dependency));
 for(const sibling of ['verith-technical-read-boundary-extra','prefix-verith-technical-read-boundary','verith-technical-read'])assert.throws(()=>check(path.join(workspace,sibling,'frontend')),/unreviewed metadata root/);
 assert.throws(()=>check('/other/verith-technical-read-boundary/frontend'),/unreviewed metadata root/);
 assert.throws(()=>check(project,'/other/dependency/node_modules'),/unreviewed metadata root/);
 assert.throws(()=>check(project,dependency,{target:'/other/node_modules'}),/code\/dependency identity mismatch/);
 assert.throws(()=>check(project,dependency,{canonical:'/other/code'}),/code\/dependency identity mismatch/);
 assert.throws(()=>check(project,dependency,{uid:9999}),/untrusted dependency metadata/);
 assert.throws(()=>check(project,dependency,{mode:0o40777}),/untrusted dependency metadata/);
});
test('CF028 actual caller accepts only the eight reviewed sibling aliases with the fixed dependency metadata',()=>{
 const source=fs.readFileSync('scripts/check-local-ports.mjs','utf8'),tree=ts.createSourceFile('caller.mjs',source,ts.ScriptTarget.Latest,true,ts.ScriptKind.JS);
 const variables=new Set(['reviewedWorkspace','reviewedCodeRoots','reviewedDependencyRoot']);
 const functions=new Set(['metadataRootFor','trusted']);
 const selected=tree.statements.filter(node=>ts.isVariableStatement(node)&&node.declarationList.declarations.some(d=>variables.has(d.name.getText(tree)))||ts.isFunctionDeclaration(node)&&functions.has(node.name?.text));
 assert.equal(selected.length,5);
 const code=selected.map(node=>node.getText(tree).replace(/^export /,'')).join('\n')+';metadataRootFor;';
 const workspace='/synthetic/workspace',project=path.join(workspace,'verith-supervisor-verification','frontend');
 const dependency=path.join(workspace,'verith','frontend','node_modules');
 function check(codeRoot,dep=dependency,{alias=dep,canonical=codeRoot,uid=1234,mode=0o40755}={}){
  const real=new Map([[codeRoot,canonical],[dep,dep],[path.join(codeRoot,'node_modules'),alias],[path.dirname(dep),path.dirname(dep)]]);
  const metadata=new Map([...real.values()].map(p=>[p,{uid,mode}]));
  const limited={realpathSync(p){assert.ok(real.has(p),'finite synthetic path only: '+p);return real.get(p);},statSync(p){assert.ok(metadata.has(p),'finite synthetic metadata only');return metadata.get(p);}};
  return vm.runInNewContext(code,{path,project,fs:limited,process:{getuid:()=>1234}},{timeout:100})(codeRoot,dep);
 }
 for(const name of ['verith-supervisor-core','verith-supervisor-verification','verith-supervisor-preparation-deadline','verith-technical-boundary','verith-technical-read-boundary','verith-technical-chart-display','verith-technical-chart-browser','verith-technical-owned-read'])assert.equal(check(path.join(workspace,name,'frontend')),path.dirname(dependency));
 const ordinary=path.join(workspace,'ordinary','frontend');assert.equal(check(ordinary,path.join(ordinary,'node_modules')),ordinary);
 for(const root of [path.join(workspace,'arbitrary','frontend'),path.join(workspace,'verith-supervisor-preparation-deadline-extra','frontend'),path.join(workspace,'prefix-verith-supervisor-preparation-deadline','frontend'),'/other/verith-supervisor-preparation-deadline/frontend',path.join(workspace,'verith-supervisor-verification-extra','frontend'),path.join(workspace,'prefix-verith-supervisor-verification','frontend'),'/other/verith-supervisor-verification/frontend'])assert.throws(()=>check(root),/unreviewed metadata root/);
 assert.throws(()=>check(project,'/other/verith/frontend/node_modules'),/unreviewed metadata root/);
 assert.throws(()=>check(project,dependency,{canonical:'/canonical/elsewhere'}),/code\/dependency identity mismatch/);
 assert.throws(()=>check(project,dependency,{alias:'/other/node_modules'}),/code\/dependency identity mismatch/);
 assert.throws(()=>check(project,dependency,{uid:9999}),/untrusted dependency metadata/);
 assert.throws(()=>check(project,dependency,{mode:0o40777}),/untrusted dependency metadata/);
});

test('CF028 actual protected invocation retains separate code/metadata roots and owned package snapshot',()=>{
 const cap=JSON.parse(fs.readFileSync(process.env.ST001_SAFE_CAP,'utf8'));
 const provenance=JSON.parse(fs.readFileSync('source-provenance.json','utf8'));
 assert.equal(cap.packageSnapshot.sourceRoot,path.dirname(cap.dependency));
 assert.equal(provenance.dependency,cap.dependency);
 assert.equal(cap.packageSnapshot.snapshot,path.join(process.cwd(),'package.json'));
 if(provenance.codeRoot!==cap.packageSnapshot.sourceRoot){
  const workspace=path.dirname(path.dirname(provenance.codeRoot));
  assert.ok(['verith-supervisor-core','verith-supervisor-verification','verith-supervisor-preparation-deadline','verith-technical-boundary','verith-technical-read-boundary','verith-technical-chart-display','verith-technical-chart-browser','verith-technical-owned-read'].map(name=>path.join(workspace,name,'frontend')).includes(provenance.codeRoot));
  assert.equal(cap.dependency,path.join(workspace,'verith','frontend','node_modules'));
 }
 console.log('CF028_ROOT_PROVENANCE '+JSON.stringify({codeRootKind:path.basename(path.dirname(provenance.codeRoot)),split:provenance.codeRoot!==cap.packageSnapshot.sourceRoot,manifestSHA:provenance.manifestSHA,workerPackageOwned:cap.packageSnapshot.snapshot===path.join(process.cwd(),'package.json')}));
});
test('CF032 exact display selection retains prior modes and only the declared readonly graph',async()=>{
 const caller=await import('../../scripts/check-local-ports.mjs');
 assert.deepEqual(caller.technicalDisplayUnit,['unit/technical/boundary-display.test.mjs','tooling/safe-checks.test.mjs']);
 assert.deepEqual(caller.technicalDisplayType,['src/features/technical/components/technical-boundary-preview.tsx']);
 assert.deepEqual(caller.technicalDisplayReadonly,['src/features/technical/lib/strict-boundary-read.ts','src/features/technical/lib/boundary-preview.ts','src/features/technical/model/types.ts','src/features/technical/lib/chart.ts','src/features/technical/components/technical-chart-panel.tsx','src/shared/lib/format.ts','tests/fixtures/cf031-technical-boundary-read.json']);
 assert.deepEqual(caller.technicalDisplayExact,[...caller.technicalDisplayType,...caller.technicalDisplayUnit.map(p=>'tests/'+p),...caller.technicalDisplayReadonly]);
 for(const mode of ['technical-display-unit','technical-display-type','technical-display-lint','technical-read-unit','technical-boundary-unit','core-browser'])assert.ok(caller.modes.includes(mode));
 for(const source of caller.technicalDisplayExact)assert.equal(sourceAllowed(source),true);
 assert.doesNotMatch(caller.technicalDisplayExact.join('\n'),/src\/app|backend\/|\.env|boundary_restore|mock-data/);
});

test('CF032 actual alias accepts only the new exact display sibling and preserves identity denials',()=>{
 const source=fs.readFileSync('scripts/check-local-ports.mjs','utf8'),tree=ts.createSourceFile('caller.mjs',source,ts.ScriptTarget.Latest,true,ts.ScriptKind.JS);
 const vars=new Set(['reviewedWorkspace','reviewedCodeRoots','reviewedDependencyRoot']),functions=new Set(['trusted','metadataRootFor']);
 const selected=tree.statements.filter(n=>ts.isVariableStatement(n)&&n.declarationList.declarations.some(d=>vars.has(d.name.getText(tree)))||ts.isFunctionDeclaration(n)&&functions.has(n.name?.text));assert.equal(selected.length,5);
 const code=selected.map(n=>n.getText(tree).replace(/^export /,'')).join('\n')+';metadataRootFor;';
 const workspace='/synthetic/workspace',project=path.join(workspace,'verith-technical-chart-display','frontend'),dependency=path.join(workspace,'verith','frontend','node_modules');
 function check(root,dep=dependency,{target=dep,canonical=root,uid=1234,mode=0o40755}={}){
  const paths=new Map([[root,canonical],[dep,dep],[path.join(root,'node_modules'),target],[path.dirname(dep),path.dirname(dep)]]);
  const fsMock={realpathSync(p){assert.ok(paths.has(p));return paths.get(p);},statSync(p){assert.ok([...paths.values()].includes(p));return {uid,mode};}};
  return vm.runInNewContext(code,{project,path,fs:fsMock,process:{getuid:()=>1234}},{timeout:100})(root,dep);
 }
 assert.equal(check(project),path.dirname(dependency));
 for(const name of ['verith-technical-chart-display-extra','prefix-verith-technical-chart-display','verith-technical-chart'])assert.throws(()=>check(path.join(workspace,name,'frontend')),/unreviewed metadata root/);
 assert.throws(()=>check('/other/verith-technical-chart-display/frontend'),/unreviewed metadata root/);
 assert.throws(()=>check(project,'/other/dependency/node_modules'),/unreviewed metadata root/);
 assert.throws(()=>check(project,dependency,{target:'/other/node_modules'}),/identity mismatch/);
 assert.throws(()=>check(project,dependency,{canonical:'/other/code'}),/identity mismatch/);
 assert.throws(()=>check(project,dependency,{uid:9999}),/untrusted dependency metadata/);
 assert.throws(()=>check(project,dependency,{mode:0o40777}),/untrusted dependency metadata/);
});

test('CF032 actual React command checks identity before/after success and failed child without a permission grant',async()=>{
 const {checkedReactCommand}=await import('../../scripts/check-local-ports.mjs');
 const original=[{relative:'react/cjs/react.production.js',version:'19.2.4',size:1,sha256:'a'.repeat(64),identity:[{dev:'1',ino:'1'}]}];
 let current=structuredClone(original),reads=0,invokes=0;
 const proof={records:original,dependency:'/synthetic/dependency',sourceRoot:'/synthetic/source',readRecords(dep,root){assert.equal(dep,'/synthetic/dependency');assert.equal(root,'/synthetic/source');reads++;return current;}};
 assert.equal(await checkedReactCommand(proof,async()=>{invokes++;return 'ok';}),'ok');
 assert.equal(reads,2);assert.equal(invokes,1);
 for(const field of ['relative','version','size','sha256','identity']){
  current=structuredClone(original);current[0][field]='drift';
  await assert.rejects(checkedReactCommand(proof,async()=>{invokes++;}),/React identity drift/);
 }
 assert.equal(invokes,1);
 current=structuredClone(original);const childError=Error('synthetic child failure');reads=0;
 await assert.rejects(checkedReactCommand(proof,async()=>{invokes++;throw childError;}),error=>error===childError);
 assert.equal(reads,2);assert.equal(invokes,2);
 current=structuredClone(original);reads=0;
 await assert.rejects(checkedReactCommand(proof,async()=>{current[0].sha256='drift';throw childError;}),error=>error instanceof AggregateError&&error.errors[0]===childError&&/React identity drift/.test(error.errors[1].message));
 assert.equal(reads,2);
});

test('CF032 display worker receives only five production records and no browser ports',()=>{
 const cap=JSON.parse(fs.readFileSync(process.env.ST001_SAFE_CAP,'utf8'));
 if(!cap.cf032Display)return;
 assert.equal(cap.workload,'unit');assert.deepEqual(cap.ports,[]);assert.ok(cap.lifetime<=120);
 assert.equal(cap.cf022Core,undefined);assert.equal(cap.cf020Planning,undefined);
 assert.deepEqual(cap.reactProduction.map(r=>r.relative),['react/cjs/react.production.js','react/cjs/react-jsx-runtime.production.js','react-dom/cjs/react-dom.production.js','react-dom/cjs/react-dom-client.production.js','scheduler/cjs/scheduler.production.js']);
 for(const record of cap.reactProduction){assert.match(record.sha256,/^[0-9a-f]{64}$/);assert.ok(record.size>0);assert.match(record.version,/^\d+\.\d+\.\d+$/);}
});
test('CF033 fixed chart selection preserves production source and exactly three vendor additions',async()=>{
 const caller=await import('../../scripts/check-local-ports.mjs');
 assert.deepEqual(caller.technicalChartUnit,['tooling/safe-checks.test.mjs']);
 assert.equal(caller.technicalChartFixture,'tests/integration/technical/chart-browser-fixture.mjs');
 assert.deepEqual(caller.chartProductionFiles,['recharts/umd/Recharts.js','lucide-react/dist/cjs/lucide-react.js','next/dist/compiled/react-is/cjs/react-is.production.js']);
 for(const mode of ['technical-chart-unit','technical-chart-lint','technical-chart-browser','core-browser','technical-display-unit','technical-read-unit'])assert.ok(caller.modes.includes(mode));
 for(const p of caller.technicalChartExact)assert.equal(sourceAllowed(p),true);
 assert.doesNotMatch(caller.technicalChartExact.join('\n'),/src\/app|backend\/|mock-data|\.env/);
});

test('CF033 actual closed production registry recognizes React19 elements/fragments and real chart/icon exports',async()=>{
 const cap=JSON.parse(fs.readFileSync(process.env.ST001_SAFE_CAP,'utf8'));
 if(!cap.cf033Chart)return;
 assert.equal(cap.workload,'unit');assert.deepEqual(cap.ports,[]);assert.ok(cap.lifetime<=120);
 const fixture=await import('../integration/technical/chart-browser-fixture.mjs');
 assert.deepEqual(fixture.registryPreflight(fixture.chartRegistry(cap)),{element:true,fragment:true,chart:true,icons:true});
 for(const field of ['sha256','relative','size']){
  const bad=structuredClone(cap);bad.chartProduction[0][field]='drift';
  assert.throws(()=>fixture.chartRegistry(bad),/CF033/);
 }
 const bad=structuredClone(cap);bad.chartMetadata[3].sha256='0'.repeat(64);assert.throws(()=>fixture.chartRegistry(bad),/CF033/);
 const require=vm.runInNewContext(fixture.moduleProgram({react:'module.exports={};'}),{},{timeout:100});
 assert.throws(()=>require('unregistered'),/unregistered module/);
 assert.throws(()=>fixture.moduleProgram({'node:fs':'module.exports={};'}),/registry invalid/);
});

test('CF033 pure route/case/body functions are import safe and retain bounded terminal input',async()=>{
 const fixture=await import('../integration/technical/chart-browser-fixture.mjs');
 for(const p of ['/technical-preview','/bundle.js','/fixture.css','/fixture-finish'])assert.equal(fixture.fixtureTarget(p).status,200);
 for(const p of ['//technical-preview','/technical-preview?x=1','/technical-preview#x','/%2e%2e/.env','http://example.test/technical-preview','/../x'])assert.equal(fixture.fixtureTarget(p).status,422);
 assert.equal(fixture.fixtureTarget('/other.js').status,404);
 const input=JSON.parse(fs.readFileSync('tests/fixtures/cf031-technical-boundary-read.json','utf8')),before=structuredClone(input),cases=fixture.fixtureCases(input);
 assert.deepEqual(input,before);assert.deepEqual(Object.keys(cases),['A','B','empty','missing','error','invalid']);
 assert.notEqual(cases.A.expected.request.data.context.report_id,cases.B.expected.request.data.context.report_id);
 assert.deepEqual(cases.A.response.data.result.charts,cases.B.response.data.result.charts);
 assert.equal(cases.error.response.data,null);assert.deepEqual(cases.empty.response.data.coverage.available_periods,[]);
 const {EventEmitter}=await import('node:events');
 const request=new EventEmitter();request.resume=()=>{};const body=fixture.readFixtureBody(request);request.emit('data',Buffer.from('{"action":"complete"}'));request.emit('end');assert.equal(await body,'{"action":"complete"}');
 let resumed=0;const large=new EventEmitter();large.resume=()=>{resumed++;};const rejected=fixture.readFixtureBody(large);large.emit('data',Buffer.alloc(1025));await assert.rejects(rejected,/body limit/);assert.equal(resumed,1);
});

test('CF036 exact owned-read three modes preserve worker/provenance graph and production records',async()=>{
 const caller=await import('../../scripts/check-local-ports.mjs');
 assert.deepEqual(caller.technicalOwnedReadUnit,['unit/technical/owned-report-read.test.mjs','unit/bff/session-proxy.test.mjs','tooling/safe-checks.test.mjs']);
 for(const mode of ['technical-owned-read-unit','technical-owned-read-type','technical-owned-read-lint','technical-chart-browser','technical-chart-unit','technical-display-unit'])assert.ok(caller.modes.includes(mode));
 for(const file of caller.technicalOwnedReadExact){assert.equal(sourceAllowed(file),true);assert.equal(sourceAllowed(file+'.adjacent'),false);}
 const source=fs.readFileSync('scripts/check-local-ports.mjs','utf8'),tree=ts.createSourceFile('caller.mjs',source,ts.ScriptTarget.Latest,true,ts.ScriptKind.JS),execute=tree.statements.find(n=>ts.isFunctionDeclaration(n)&&n.name?.text==='execute');
 const declaration=execute.body.statements.find(n=>ts.isVariableStatement(n)&&n.declarationList.declarations.some(d=>d.name.getText(tree)==='technicalOwnedReadOnly')),selection=execute.body.statements.find(n=>ts.isIfStatement(n)&&n.expression.getText(tree)==='technicalOwnedReadOnly');
 for(const mode of ['unit','type','lint']){const ctx={selected:['technical-owned-read-'+mode]};vm.runInNewContext(declaration.getText(tree)+'\n'+selection.getText(tree),ctx,{timeout:100});assert.deepEqual(Array.from(ctx.selected),[mode]);}
 assert.match(source,/technicalOwnedReadOnly\?technicalOwnedReadUnit/);assert.match(source,/technicalOwnedReadOnly\?\['-p','tsconfig.cf036.json'\]/);assert.match(source,/\(technicalDisplayOnly\|\|technicalOwnedReadOnly\)&&selected\[0\]==='unit'\?displayReactRecords/);
 const cap=JSON.parse(fs.readFileSync(process.env.ST001_SAFE_CAP,'utf8'));if(cap.cf032Display){assert.deepEqual(cap.ports,[]);assert.equal(cap.reactProduction.length,5);}
});
test('CF036 exact sibling permits only reviewed owned-read root and existing fixed dependency',()=>{
 const source=fs.readFileSync('scripts/check-local-ports.mjs','utf8'),tree=ts.createSourceFile('caller.mjs',source,ts.ScriptTarget.Latest,true,ts.ScriptKind.JS),vars=new Set(['reviewedWorkspace','reviewedCodeRoots','reviewedDependencyRoot']),functions=new Set(['trusted','metadataRootFor']);
 const selected=tree.statements.filter(n=>ts.isVariableStatement(n)&&n.declarationList.declarations.some(d=>vars.has(d.name.getText(tree)))||ts.isFunctionDeclaration(n)&&functions.has(n.name?.text));assert.equal(selected.length,5);
 const code=selected.map(n=>n.getText(tree).replace(/^export /,'')).join('\n')+';metadataRootFor;',workspace='/synthetic/workspace',project=path.join(workspace,'verith-technical-owned-read','frontend'),dependency=path.join(workspace,'verith','frontend','node_modules');
 function check(root,dep=dependency,{target=dep,canonical=root,uid=1234,mode=0o40755}={}){const paths=new Map([[root,canonical],[dep,dep],[path.join(root,'node_modules'),target],[path.dirname(dep),path.dirname(dep)]]);return vm.runInNewContext(code,{project,path,fs:{realpathSync(p){assert.ok(paths.has(p));return paths.get(p);},statSync(){return {uid,mode};}},process:{getuid:()=>1234}},{timeout:100})(root,dep);}
 assert.equal(check(project),path.dirname(dependency));for(const root of [path.join(workspace,'verith-technical-owned-read-extra','frontend'),path.join(workspace,'prefix-verith-technical-owned-read','frontend'),'/other/verith-technical-owned-read/frontend'])assert.throws(()=>check(root),/unreviewed metadata root/);
 assert.throws(()=>check(project,'/other/node_modules'),/unreviewed metadata root/);assert.throws(()=>check(project,dependency,{target:'/other/node_modules'}),/identity mismatch/);assert.throws(()=>check(project,dependency,{canonical:'/other/root'}),/identity mismatch/);assert.throws(()=>check(project,dependency,{uid:9999}),/untrusted/);assert.throws(()=>check(project,dependency,{mode:0o40777}),/untrusted/);
});
test('CF036 fixed browser target validates only owned pages/API queries and nonce-control modes',async()=>{
 const fixture=await import('../integration/technical/chart-browser-fixture.mjs'),id='00000000-0000-4000-8000-000000000006';
 for(const target of ['/reports/technical','/reports/technical/'+id,'/api/auth/session','/api/private/technical/owned-reports?stock_code=005930&limit=20&offset=0','/api/private/technical/owned-reports/'+id])assert.equal(fixture.fixtureTarget(target).status,200);
 for(const target of ['/reports/technical?owner=x','/reports/technical?limit=0','/reports/technical?limit=10&limit=10','/reports/technical/'+id+'?x=1','/api/private/technical/owned-reports?offset=10001','/api/auth/session?x=1','/bundle.js?x=1','/fixture-owned-mode?mode=normal'])assert.notEqual(fixture.fixtureTarget(target).status,200);
 assert.equal(fixture.ownedMode('{"mode":"slow"}'),'slow');for(const body of ['{}','{"mode":"private"}','{"mode":"normal","url":"https://other"}'])assert.throws(()=>fixture.ownedMode(body),/mode invalid/);
 const source=fs.readFileSync('tests/integration/technical/chart-browser-fixture.mjs','utf8');assert.match(source,/listGET:0,detailGET:0,modePOST:0/);assert.match(source,/setTimeout\(resolve,1200\)/);assert.match(source,/ownedSessionReads%2===0/);assert.match(source,/OwnedReportView/);
});

test('CF036 separate owned counts preserve the original terminal receipt schema',async()=>{
 const caller=await import('../../scripts/check-local-ports.mjs'),proof={nonce:'synthetic',pid:123,cwd:'/owned',port:12345},value={schema:'cf036.browser-counts.v1',...proof,counts:{listGET:2,detailGET:3,modePOST:1},mode:'normal'};
 assert.deepEqual(caller.validateOwnedChartCounts(value,proof),value);for(const mutate of [v=>v.counts.listGET=-1,v=>v.counts.unapproved=1,v=>v.pid++,v=>v.mode='other',v=>v.extra=true]){const bad=structuredClone(value);mutate(bad);assert.throws(()=>caller.validateOwnedChartCounts(bad,proof),/owned counts mismatch/);}
});
