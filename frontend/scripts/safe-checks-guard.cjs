'use strict';
// Synchronous --require preload must run before ESM/application collection.
// Only this CJS file's exact node: builtins are excepted; all other require stays error.
/* eslint @typescript-eslint/no-require-imports: ["error", {"allow": ["^node:(fs|path|net|tls|dns|dgram|child_process|http|https|module|url|worker_threads|crypto)$"]}] */
// Preload for owned check workers only. OS profile is mandatory, not replaced here.
const fs = require('node:fs');
const path = require('node:path');
const net = require('node:net');
const tls = require('node:tls');
const dns = require('node:dns');
const dgram = require('node:dgram');
const cp = require('node:child_process');
const http = require('node:http');
const https = require('node:https');
const {syncBuiltinESMExports} = require('node:module');
const crypto = require('node:crypto');

let installed;
const diagnosticAPIs=new Set(['readFile','readFileSync','createReadStream','readdir','readdirSync','open','openSync','writeFile','writeFileSync','appendFile','appendFileSync','mkdir','mkdirSync','rm','rmSync','unlink','unlinkSync','createWriteStream','promises.readFile','promises.readdir','promises.open','promises.writeFile','promises.appendFile','promises.mkdir','promises.rm','promises.unlink','other']);
function privateDiagnosticName(value){
  const parts=value.startsWith('/private/')?value.split('/').slice(2):value.split('/');
  const names=new Set(['private','secret','secrets','key','keys','credential','credentials','dump','dumps','backup','backups','log','logs']);
  return parts.some(part=>names.has(part.toLowerCase())||part.toLowerCase().startsWith('.env')||part.toLowerCase().startsWith('credentials')||part.toLowerCase().split('.').slice(1).some(s=>['key','pem','p12','sql','dump','bak','backup','log'].includes(s)));
}
function createDiagnostics(context,{maxEvents=256}={}){
  const d=context.diagnostics;
  if(!d||!/^[a-f0-9]{64}$/.test(d.key)||!/^[a-f0-9]{24}$/.test(d.run)||!Array.isArray(d.copySources)||d.copySources.length>1024||!['root','dependency','sourceRoot'].every(k=>typeof context[k]==='string'&&path.isAbsolute(context[k]))||!Array.isArray(context.runtime)||context.runtime.length>8||!context.runtime.every(p=>typeof p==='string'&&path.isAbsolute(p))||!['entry-worker','next-worker'].includes(context.workerRole)||!['self-test','unit','build','local-http','type','lint','all'].includes(context.workload)||!Number.isInteger(maxEvents)||maxEvents<1||maxEvents>256)throw Error('SAFE_CHECK_DENIED: diagnostic configuration');
  const key=Buffer.from(d.key,'hex'),events=new Map(),source=context.sourceRoot;
  const copy=new Set(d.copySources);
  for(const name of copy)if(typeof name!=='string'||name.length>256||path.isAbsolute(name)||name.split('/').some(p=>!p||p==='.'||p==='..'))throw Error('SAFE_CHECK_DENIED: diagnostic copy manifest');
  const within=(p,parent)=>typeof parent==='string'&&(p===parent||p.startsWith(parent+path.sep));
  const id=(domain,value)=>crypto.createHmac('sha256',key).update(domain+'\0'+value).digest('hex');
  function role(value){
    if(typeof value!=='string')return 'unknown';
    if(within(value,context.root))return 'owned-root';
    if(within(value,context.dependency))return 'verified-dependency';
    if(context.runtime.some(p=>within(value,p)))return 'reviewed-runtime';
    if(within(value,source))return 'original-project';
    if(within(value,path.dirname(source)))return 'original-repo';
    return 'outside';
  }
  function describe({lexical,canonical,api='other',write=false,stack=''}){
    if(typeof canonical!=='string'||typeof lexical!=='string'||canonical.length>4096||lexical.length>4096||typeof stack!=='string'||stack.length>32000)throw Error('SAFE_CHECK_DENIED: diagnostic normalization');
    const relative=within(canonical,source)?path.relative(source,canonical):null;
    const knownCopy=relative!==null&&copy.has(relative),privateNameMatch=privateDiagnosticName(canonical);
    let label=null;
    if(canonical==='/proc/self/cgroup')label='telemetry-container-probe:cgroup';
    for(const name of ['package.json','package-lock.json','tsconfig.json','next.config.ts','postcss.config.mjs','eslint.config.mjs'])if(canonical===path.join(source,name))label='original-project-metadata:'+name;
    if(knownCopy&&relative==='src/app/api/private/[...path]/route.ts')label='public-bff-private-route';
    else if(knownCopy&&!privateNameMatch&&!label)label='copied-source:'+relative;
    // Only fixed reviewed dependency call sites determine public caller families.
    const docker=stack.includes(context.dependency+'/next/dist/compiled/is-docker/index.js:1:');
    const hash=stack.includes(context.dependency+'/next/dist/compiled/webpack/bundle5.js:29:296487');
    return {schema:1,run:d.run,workerRole:context.workerRole,workload:context.workload,
      api:diagnosticAPIs.has(api)?api:'other',access:write?'write':'read',callerFamily:docker?'telemetry-container-detection':hash?'webpack-file-hash':'other',
      callerId:id('caller',stack),label,targetId:id('target',canonical),...(lexical!==canonical?{lexicalId:id('target',lexical)}:{}),
      role:role(canonical),privateNameMatch,knownCopy};
  }
  return Object.freeze({describe,record(input){const event=describe(input),token=JSON.stringify(event);if(!events.has(token)&&events.size>=maxEvents)throw Error('SAFE_CHECK_DENIED: diagnostic event budget');const old=events.get(token);events.set(token,{...event,count:(old?.count??0)+1});if(events.get(token).count>1000000)throw Error('SAFE_CHECK_DENIED: diagnostic count budget');return event;},snapshot:()=>[...events.values()].map(event=>({...event}))});
}
function journalLine(event,observation,used,limit=2000000){
  if(!['validated-bootstrap','metadata-hit','denied','original-raw-dispatch','expected-negative','exit'].includes(event)||!Number.isSafeInteger(used)||used<0||!Number.isSafeInteger(limit)||limit<1||limit>2000000)throw Error('SAFE_CHECK_DENIED: observation journal configuration');
  const line=JSON.stringify({event,...observation})+'\n';
  if(used+Buffer.byteLength(line)>limit)throw Error('SAFE_CHECK_DENIED: observation journal limit');
  return line;
}
const packageSHA='5dcc4949fad70a41d4c4fe5639f63931fcaf99accd3019a53052c00a4e697ef5';
function manifestIdentity(filename,io=fs){
  const pieces=filename.split(path.sep).filter(Boolean),rows=[];
  for(let n=0;n<=pieces.length;n++){
    const s=io.lstatSync(path.sep+pieces.slice(0,n).join(path.sep),{bigint:true});
    if(s.isSymbolicLink()||n===pieces.length&&(!s.isFile()||s.nlink!==1n)||n<pieces.length&&!s.isDirectory())throw Error('SAFE_CHECK_DENIED: snapshot identity');
    rows.push({dev:String(s.dev),ino:String(s.ino),mode:String(s.mode),...(n===pieces.length?{size:String(s.size),mtime:String(s.mtimeNs),ctime:String(s.ctimeNs),nlink:String(s.nlink)}:{})});
  }
  return rows;
}
function readPackageSnapshot(cap,io){
  const p=cap.packageSnapshot,fail=()=>{throw Error('SAFE_CHECK_DENIED: snapshot capability/fingerprint');};
  if(!p||Object.keys(p).sort().join(',')!==['sourceRoot','literal','snapshot','sourceIdentity','snapshotIdentity','length','sha256'].sort().join(','))fail();
  const root=io.realpathSync.native(cap.root),dependency=io.realpathSync.native(cap.dependency);
  if(!path.isAbsolute(p.sourceRoot)||p.sourceRoot!==io.realpathSync.native(p.sourceRoot)||p.sourceRoot!==path.dirname(dependency)||io.realpathSync.native(path.join(p.sourceRoot,'node_modules'))!==dependency||p.literal!==path.join(p.sourceRoot,'package.json')||p.snapshot!==path.join(root,'package.json')||p.length!==707||p.sha256!==packageSHA)fail();
  const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
  if(!same(manifestIdentity(p.literal,io),p.sourceIdentity)||!same(manifestIdentity(p.snapshot,io),p.snapshotIdentity))fail();
  // Only the owned snapshot is opened; never open p.literal in any worker.
  const fd=io.openSync(p.snapshot,fs.constants.O_RDONLY|fs.constants.O_NOFOLLOW|fs.constants.O_NONBLOCK);
  let bytes;
  try{
    const s=io.fstatSync(fd,{bigint:true}),last=p.snapshotIdentity.at(-1);
    if(!s.isFile()||s.nlink!==1n||String(s.dev)!==last.dev||String(s.ino)!==last.ino)fail();
    bytes=io.readFileSync(fd);
  }finally{io.closeSync(fd);}
  if(bytes.length!==p.length||crypto.createHash('sha256').update(bytes).digest('hex')!==p.sha256||!same(manifestIdentity(p.snapshot,io),p.snapshotIdentity)||!same(manifestIdentity(p.literal,io),p.sourceIdentity))fail();
  return Buffer.from(bytes);
}
function loadPackageSnapshot(cap,io=fs){
  try{return readPackageSnapshot(cap,io);}
  catch{throw Error('SAFE_CHECK_DENIED: snapshot capability/fingerprint');}
}
function packageResponder(bytes,literal,sha256,deny,onHit=()=>{}){
  const immutable=Buffer.from(bytes),hits={readFile:0,readFileSync:0,promisesReadFile:0};
  function optionsFor(api,options){
    if(options===undefined||options===null)options={};
    if(typeof options==='string')options={encoding:options};
    if(typeof options!=='object'||![Object.prototype,null].includes(Object.getPrototypeOf(options))||Reflect.ownKeys(options).some(k=>!['encoding','flag',...(api==='readFileSync'?[]:['signal'])].includes(k)))return deny('snapshot unsupported options');
    const encoding=options.encoding??null;
    if(encoding!==null&&(typeof encoding!=='string'||!Buffer.isEncoding(encoding)))return deny('snapshot encoding');
    if(options.flag!==undefined&&options.flag!=='r')return deny('snapshot non-read flag');
    const signal=options.signal;
    if(signal!==undefined){try{Object.getOwnPropertyDescriptor(AbortSignal.prototype,'aborted').get.call(signal);}catch{return deny('snapshot signal');}}
    return {encoding,signal};
  }
  const matches=value=>typeof value==='string'&&value===literal;
  function prepare(api,value,options){
    if(!matches(value))return deny('snapshot request shape');
    return optionsFor(api,options);
  }
  function result(api,parsed){
    if(parsed.signal?.aborted)throw Object.assign(new Error('The operation was aborted'),{name:'AbortError',code:'ABORT_ERR',cause:parsed.signal.reason});
    hits[api]++;
    onHit(api);
    return parsed.encoding===null?Buffer.from(immutable):immutable.toString(parsed.encoding);
  }
  return Object.freeze({matches,
    sync:(value,options)=>result('readFileSync',prepare('readFileSync',value,options)),
    callback(value,options,callback){
      if(typeof options==='function'){callback=options;options=undefined;}
      if(typeof callback!=='function')throw Object.assign(new TypeError('Callback must be a function'),{code:'ERR_INVALID_ARG_TYPE'});
      const parsed=prepare('readFile',value,options);
      // Do not invoke user callbacks in a catch that could turn their throw into a second call.
      setImmediate(()=>{let data;try{data=result('readFile',parsed);}catch(error){callback(error);return;}callback(null,data);});
    },
    promise:(value,options)=>new Promise((resolve,reject)=>{const parsed=prepare('promisesReadFile',value,options);setImmediate(()=>{try{resolve(result('promisesReadFile',parsed));}catch(error){reject(error);}});}),
    ledger:()=>({scope:'verified-original-package-metadata',sha256,hits:{...hits}}),
  });
}
function deniedFileLabel(value,root,dependency) {
  // No arbitrary filename, home path, credential value, or file contents in diagnostics.
  const within=(p,parent)=>p===parent||p.startsWith(parent+path.sep);
  const pieces=value.split(path.sep),parts=value.startsWith('/private/')?pieces.slice(2):pieces;
  if(parts.some(p=>p.startsWith('.env')||/^(private|secrets?|keys?|credentials?)(\.|$)/i.test(p)))return 'private-path-redacted';
  const scope=within(value,root)?'owned-root':within(value,dependency)?'dependency':within(value,path.dirname(dependency))?'original-project':'outside';
  const publicNames=new Set(['package.json','tsconfig.json','next.config.ts','postcss.config.mjs']);
  const leaf=path.basename(value);
  if(scope==='original-project'&&value===path.join(path.dirname(dependency),'package.json'))return 'original-project-root:package.json';
  for(const name of ['package-lock.json','tsconfig.json','next.config.ts','postcss.config.mjs','eslint.config.mjs'])if(value===path.join(path.dirname(dependency),name))return 'original-project-root:'+name;
  for(const name of ['package.json','package-lock.json','tsconfig.json'])if(value===path.join(path.dirname(path.dirname(dependency)),name))return 'original-repo-root:'+name;
  return scope+(publicNames.has(leaf)?':public-manifest-relative-location-redacted':':target-redacted');
}
function validateDemoFlag(value){
  if(value!==undefined&&value!=='true'&&value!=='false')throw Error('SAFE_CHECK_DENIED: demo flag');
  return value;
}
function forkPlan(modulePath,args,options,cap,real=fs.realpathSync.native){
  const target=real(path.join(cap.dependency,'next/dist/compiled/jest-worker/processChild.js'));
  if(typeof modulePath!=='string'||real(modulePath)!==target||!Array.isArray(args)||args.length!==0)throw Error('SAFE_CHECK_DENIED: fork target/argv');
  if(!options||real(options.cwd)!==real(cap.root)||options.detached||options.execPath&&options.execPath!==process.execPath||options.serialization&&options.serialization!=='json')throw Error('SAFE_CHECK_DENIED: fork execution options');
  const allowed=new Set(['cwd','env','execArgv','silent','stdio','detached','execPath','serialization']);
  if(Object.keys(options).some(k=>!allowed.has(k)))throw Error('SAFE_CHECK_DENIED: fork options');
  if(options.stdio && JSON.stringify(options.stdio)!==JSON.stringify(['pipe','pipe','pipe','ipc']))throw Error('SAFE_CHECK_DENIED: fork IPC');
  const extra=options.execArgv??[];
  if(!Array.isArray(extra)||extra.some(a=>!['--enable-source-maps'].includes(a)))throw Error('SAFE_CHECK_DENIED: fork execArgv');
  const env={};
  for(const k of ['LANG','TZ','HOME','TMPDIR','PATH','NEXT_TELEMETRY_DISABLED','NO_UPDATE_NOTIFIER','ST001_SAFE_CAP','NODE_ENV','BACKEND_URL','NEXT_PUBLIC_API_URL','AI_SUPERVISOR_URL'])if(cap.environment[k]!==undefined)env[k]=cap.environment[k];
  const demo=validateDemoFlag(cap.environment.FLOW_SYNTHETIC_DEMO_ENABLED);
  if(demo!==undefined)env.FLOW_SYNTHETIC_DEMO_ENABLED=demo;
  // Reconstruct the one mandatory preload; never forward Next's spread parent env.
  env.NODE_OPTIONS='--require='+cap.guard;
  env.OPENSSL_CONF='/dev/null';
  const input=options.env??{};
  if(input.ST001_SAFE_CAP!==env.ST001_SAFE_CAP)throw Error('SAFE_CHECK_DENIED: fork capability');
  if(Object.prototype.hasOwnProperty.call(input,'FLOW_SYNTHETIC_DEMO_ENABLED')&&validateDemoFlag(input.FLOW_SYNTHETIC_DEMO_ENABLED)!==demo)throw Error('SAFE_CHECK_DENIED: demo flag');
  if(input.JEST_WORKER_ID!==undefined){if(!/^[1-9][0-9]*$/.test(input.JEST_WORKER_ID))throw Error('SAFE_CHECK_DENIED: worker id');env.JEST_WORKER_ID=input.JEST_WORKER_ID;}
  if(input.IS_NEXT_WORKER==='true')env.IS_NEXT_WORKER='true';
  if(input.NEXT_PRIVATE_BUILD_WORKER!==undefined){if(input.NEXT_PRIVATE_BUILD_WORKER!=='1')throw Error('SAFE_CHECK_DENIED: build worker marker');env.NEXT_PRIVATE_BUILD_WORKER='1';}
  if(input.__NEXT_PRERENDER_CLIENT_ASSET_SUFFIX!==undefined){if(input.__NEXT_PRERENDER_CLIENT_ASSET_SUFFIX!=='')throw Error('SAFE_CHECK_DENIED: unreviewed deployment suffix');env.__NEXT_PRERENDER_CLIENT_ASSET_SUFFIX='';}
  if(input.FORCE_COLOR==='1')env.FORCE_COLOR='1';
  return {module:target,args:[],options:{cwd:cap.root,execPath:process.execPath,execArgv:extra,env,silent:true,stdio:['pipe','pipe','pipe','ipc'],detached:false,serialization:'json'}};
}
function install(cap) {
  const real = fs.realpathSync.native;
  const root = real(cap.root), dependency = real(cap.dependency);
  const runtime = cap.runtime.map(value => real(value));
  const violations = [];
  const within = (value, parent) => value === parent || value.startsWith(parent + path.sep);
  const diagnostics=createDiagnostics({root,dependency,runtime,sourceRoot:cap.packageSnapshot.sourceRoot,diagnostics:cap.diagnostics,workerRole:process.env.IS_NEXT_WORKER==='true'?'next-worker':'entry-worker',workload:cap.workload});
  let deniedTotal=0,expectedNegatives=0,persist=()=>{},diagnosing=false,diagnosticFailures=0;
  const deny = (kind,target) => {
    deniedTotal++;violations.push(kind);
    if(target){try{if(diagnosing)throw Error('recursive diagnostic');diagnosing=true;diagnostics.record({...target,stack:new Error().stack});}catch{diagnosticFailures++;}finally{diagnosing=false;}}
    persist('denied');throw new Error('SAFE_CHECK_DENIED: '+kind);
  };
  const observed={rawDispatches:0,rawOriginalDispatches:0,rawOriginalDenied:0,rawAPIs:{}};
  const originalFDs=new Set(),literal=cap.packageSnapshot?.literal;
  const originalTarget=value=>{
    if(typeof value==='number')return originalFDs.has(value);
    try{const name=value instanceof URL?require('node:url').fileURLToPath(value):Buffer.isBuffer(value)?value.toString():value;return typeof name==='string'&&path.resolve(name)===literal;}catch{return false;}
  };
  function rawConsume(api,original,receiver,value,args){
    observed.rawDispatches++;observed.rawAPIs[api]=(observed.rawAPIs[api]??0)+1;
    const isOriginal=originalTarget(value);if(isOriginal)observed.rawOriginalDispatches++;
    if(isOriginal)persist('original-raw-dispatch');
    const result=original.call(receiver,value,...args);
    if(api.endsWith('openSync')&&isOriginal)originalFDs.add(result);
    return result;
  }
  const snapshotIO={...fs,
    openSync(value,...args){return rawConsume('bootstrap.openSync',fs.openSync,fs,value,args);},
    readFileSync(value,...args){return rawConsume('bootstrap.readFileSync',fs.readFileSync,fs,value,args);},
  };
  const snapshot=packageResponder(loadPackageSnapshot(cap,snapshotIO),literal,cap.packageSnapshot.sha256,deny,()=>persist('metadata-hit'));
  const journal=fs.openSync(path.join(root,'.snapshot-ledger-'+process.pid+'-'+crypto.randomBytes(8).toString('hex')+'.jsonl'),fs.constants.O_WRONLY|fs.constants.O_CREAT|fs.constants.O_EXCL|fs.constants.O_NOFOLLOW,0o600);
  const writeJournal=fs.writeSync,closeJournal=fs.closeSync;
  let journalBytes=0;
  const observation=()=>({scope:'instrumented-js-fs-consumer-dispatch-only',...observed,rawAPIs:{...observed.rawAPIs},snapshot:snapshot.ledger(),deniedTotal,expectedNegatives,violations:[...violations],diagnosticFailures,diagnostics:diagnostics.snapshot(),native:'not-observed'});
  persist=event=>{const line=journalLine(event,observation(),journalBytes);journalBytes+=Buffer.byteLength(line);writeJournal(journal,line);};
  persist('validated-bootstrap');
  function file(value, write = false, api='other') {
    if (typeof value === 'number') return value;
    let valuePath = path.resolve(value instanceof URL ? require('node:url').fileURLToPath(value) : String(value));
    const lexical=valuePath;
    if (valuePath.split(path.sep).some(part => part.startsWith('.env'))) return deny('private file',{lexical,canonical:valuePath,api,write});
    // Resolve existing parents too, including the sole owned node_modules link.
    let parent = valuePath, tail = [];
    while (!fs.existsSync(parent)) { tail.unshift(path.basename(parent)); parent = path.dirname(parent); }
    valuePath = path.join(real(parent), ...tail);
    if (write ? !within(valuePath, root) : ![root, dependency, ...runtime].some(p => within(valuePath, p))) {
      if(!write&&valuePath===literal)observed.rawOriginalDenied++;
      deny('file outside capability',{lexical,canonical:valuePath,api,write});
    }
    return value;
  }
  for (const name of ['readFileSync','readFile','createReadStream','readdirSync','readdir']) {
    const original = fs[name];
    fs[name] = function(value,...args) {
      if(snapshot.matches(value)&&name==='readFileSync')return snapshot.sync(value,...args);
      if(snapshot.matches(value)&&name==='readFile')return snapshot.callback(value,...args);
      file(value,false,name);return rawConsume(name,original,this,value,args);
    };
  }
  for (const name of ['writeFileSync','writeFile','appendFileSync','appendFile','mkdirSync','mkdir','rmSync','rm','unlinkSync','unlink','createWriteStream']) {
    const original = fs[name];
    fs[name] = function(value,...args) {file(value,true,name);return original.call(this,value,...args);};
  }
  for (const name of ['open','openSync']) {
    const original=fs[name];
    fs[name]=function(value,flags,...args){file(value,typeof flags==='number' ? Boolean(flags & (fs.constants.O_WRONLY|fs.constants.O_RDWR|fs.constants.O_CREAT)) : /[wa+]/.test(flags),name);return rawConsume(name,original,this,value,[flags,...args]);};
  }
  for (const name of ['readFile','readdir','writeFile','appendFile','mkdir','rm','unlink','open']) {
    const original=fs.promises[name];
    fs.promises[name]=function(value,...args){if(name==='readFile'&&snapshot.matches(value))return snapshot.promise(value,...args);file(value,!['readFile','readdir'].includes(name) && (name!=='open' || /[wa+]/.test(String(args[0]))),'promises.'+name);return ['readFile','open','readdir'].includes(name)?rawConsume('promises.'+name,original,this,value,args):original.call(this,value,...args);};
  }
  function endpoint(host,port) {
    if (!['127.0.0.1','::1','localhost'].includes(host) || !cap.ports.includes(Number(port))) deny('network target');
  }
  const originalConnect=net.Socket.prototype.connect;
  net.Socket.prototype.connect=function(...args){
    const options=Array.isArray(args[0]) ? args[0][0] : args[0];
    if(typeof options==='object') {if(options.path)deny('Unix socket');endpoint(options.host??'localhost',options.port);}
    else endpoint(typeof args[1]==='string'?args[1]:'localhost',options);
    return originalConnect.apply(this,args);
  };
  const originalListen=net.Server.prototype.listen;
  net.Server.prototype.listen=function(...args){
    const first=args[0];
    endpoint(typeof first==='object'?first.host:args[1],typeof first==='object'?first.port:first);
    return originalListen.apply(this,args);
  };
  for(const name of ['lookup','resolve','resolve4','resolve6','reverse']) {
    dns[name]=()=>deny('DNS'); if(dns.promises[name])dns.promises[name]=()=>deny('DNS');
  }
  // Literal loopback addresses avoid OS DNS. Canonical localhost is pinned below.
  dns.lookup=(host,options,callback)=>{
    if(typeof options==='function'){callback=options;options={};}
    if(!['localhost','127.0.0.1','::1'].includes(host))return deny('DNS');
    const family=options?.family===6?6:4,address=family===6?'::1':'127.0.0.1';
    queueMicrotask(()=>options?.all ? callback(null,[{address,family}]) : callback(null,address,family));
  };
  dgram.createSocket=()=>deny('UDP');tls.connect=()=>deny('TLS');
  for(const transportModule of [http,https]) for(const name of ['request','get']) {
    const original=transportModule[name];
    transportModule[name]=function(target,...args){
      if(typeof target==='object' && !(target instanceof URL)) {if(target.socketPath)deny('Unix socket');endpoint(target.hostname??target.host??'localhost',target.port??(transportModule===https?443:80));}
      else {const u=new URL(target);endpoint(u.hostname,u.port|| (u.protocol==='https:'?443:80));}
      return original.call(this,target,...args);
    };
  }
  const originalFetch=global.fetch;
  global.fetch=async(input,options={})=>{
    const u=new URL(typeof input==='string'||input instanceof URL?input:input.url);endpoint(u.hostname,u.port||80);
    let response=await originalFetch(input,{...options,redirect:'manual',signal:options.signal??AbortSignal.timeout(5000)});
    if(options.redirect==='manual')return response;
    for(let i=0;i<5 && [301,302,303,307,308].includes(response.status);i++){
      const location=new URL(response.headers.get('location'),response.url);endpoint(location.hostname,location.port||80);
      if(location.origin!==u.origin)deny('cross-origin redirect');
      response=await originalFetch(location,{...options,redirect:'manual',signal:AbortSignal.timeout(5000)});
    }
    return response;
  };
  // Exact reviewed runtime children only, all inherit preload and OS profile.
  const ownedProcesses=new Map();
  const originalSpawn=cp.spawn;
  const originalFork=cp.fork;
  cp.spawn=function(executable,args,options={}){
    if(executable!==process.execPath || !Array.isArray(args) || !options.cwd || options.detached || !within(real(options.cwd),root))deny('child launch');
    if(typeof args[0]!=='string' || !path.isAbsolute(args[0]) || !within(real(args[0]),dependency) || !/next\/dist\/(bin\/next|compiled\/jest-worker\/processChild\.js)$/.test(real(args[0])))deny('unreviewed child argv');
    if(options.env?.NODE_OPTIONS!==process.env.NODE_OPTIONS || options.env?.ST001_SAFE_CAP!==process.env.ST001_SAFE_CAP || options.env?.OPENSSL_CONF!=='/dev/null')deny('child preload/native config missing');
    const child=originalSpawn.call(this,executable,args,options);
    ownedProcesses.set(child.pid,child);child.once('close',()=>ownedProcesses.delete(child.pid));return child;
  };
  const originalExecFileSync=cp.execFileSync;
  cp.execFileSync=function(executable,args,options={}){
    const candidate=ownedProcesses.get(Number(args?.[3]));
    const ownPid=Boolean(candidate && candidate.exitCode===null && candidate.signalCode===null);
    const shape=executable==='/bin/ps' && args?.[0]==='-o' && args?.[1]==='pgid=' && args?.[2]==='-p' && args.length===4 || executable==='/usr/sbin/lsof' && args?.[0]==='-nP' && args?.[1]==='-a' && args?.[2]==='-p' && args.length===7;
    if(!ownPid||!shape)deny('process execution');
    return originalExecFileSync.call(this,executable,args,{...options,timeout:2000});
  };
  cp.fork=function(modulePath,args,options){
    let plan;
    try{plan=forkPlan(modulePath,args,options,{...cap,environment:process.env,guard:__filename});}
    catch{deny('fork target/options');}
    const child=originalFork.call(this,plan.module,plan.args,plan.options);
    ownedProcesses.set(child.pid,child);child.once('close',()=>ownedProcesses.delete(child.pid));return child;
  };
  for(const name of ['exec','execSync','execFile','spawnSync'])cp[name]=()=>deny('process execution');
  const worker=require('node:worker_threads');
  const OriginalWorker=worker.Worker;
  worker.Worker=class extends OriginalWorker {
    constructor(filename,options={}){
      file(filename);if(options.eval || !String(filename).includes('next/'))deny('worker launch');
      super(filename,{...options,env:process.env,execArgv:['--require',__filename]});
    }
  };
  const started=Date.now(),parent=process.ppid;
  setInterval(()=>{if(process.ppid!==parent || Date.now()-started>cap.lifetime*1000)process.exit(79);},200).unref();
  process.on('exit',()=>{try{persist('exit');closeJournal(journal);console.log('ST001_SNAPSHOT '+JSON.stringify(observation()));}catch{process.exitCode=1;}if(violations.length||observed.rawOriginalDispatches||deniedTotal!==expectedNegatives||diagnosticFailures)process.exitCode=1;});
  syncBuiltinESMExports();
  return {file,endpoint,violations,observation,expectedNegative(){expectedNegatives++;persist('expected-negative');}};
}

module.exports={install,forkPlan,validateDemoFlag,deniedFileLabel,manifestIdentity,loadPackageSnapshot,packageResponder,createDiagnostics,journalLine,observation(){if(!installed)throw Error('missing installed guard');return installed.observation();},expected(probe){if(!installed)throw Error('missing installed guard');const before=installed.violations.length;try{probe();throw Error('probe unexpectedly allowed');}catch(error){if(!String(error.message).startsWith('SAFE_CHECK_DENIED:')||installed.violations.length!==before+1)throw error;installed.violations.splice(before);installed.expectedNegative();}}};
if(process.env.ST001_SAFE_CAP){
  validateDemoFlag(process.env.FLOW_SYNTHETIC_DEMO_ENABLED);
  const cap=JSON.parse(fs.readFileSync(process.env.ST001_SAFE_CAP,'utf8'));
  const allowed=new Set(['LANG','TZ','HOME','TMPDIR','PATH','NEXT_TELEMETRY_DISABLED','NO_UPDATE_NOTIFIER','NODE_OPTIONS','ST001_SAFE_CAP','BACKEND_URL','NEXT_PUBLIC_API_URL','AI_SUPERVISOR_URL','NODE_ENV','__CF_USER_TEXT_ENCODING','OPENSSL_CONF','IS_NEXT_WORKER','JEST_WORKER_ID','FORCE_COLOR','NEXT_PRIVATE_BUILD_WORKER','__NEXT_PRERENDER_CLIENT_ASSET_SUFFIX','FLOW_SYNTHETIC_DEMO_ENABLED']);
  for(const key of Object.keys(process.env))if(!allowed.has(key))delete process.env[key];
  if(process.env.OPENSSL_CONF!=='/dev/null')throw Error('SAFE_CHECK_DENIED: unpinned OpenSSL startup config');
  installed=install(cap);
}
