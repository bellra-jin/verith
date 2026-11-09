// ST-001 3-B. Public launch must use env -i with the verified absolute Node.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {spawn,execFileSync} from 'node:child_process';

export const modes=['self-test','unit','local-http','build','type','lint','analysis-unit','analysis-lint','analysis-type','fundamental-unit','fundamental-type','fundamental-lint','flow-review-unit','flow-review-type','flow-review-lint','flow-review-browser'];
const project=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const repo=path.dirname(project);
const unit=['unit/bff/disabled-routes.test.mjs','unit/bff/session-proxy.test.mjs','unit/config/ports.test.mjs','tooling/safe-checks.test.mjs','unit/flow/observation.test.mjs','unit/flow/synthetic-demo.test.mjs'];
const fundamentalUnit=['unit/fundamental/analysis-request.test.mjs','unit/bff/session-proxy.test.mjs','unit/config/ports.test.mjs'];
const fundamentalType=["src/app/fundamental/page.tsx", "src/app/page.tsx", "src/app/reports/fundamental/[reportId]/page.tsx", "src/features/fundamental/components/analysis-request.tsx", "src/features/fundamental/components/fundamental-report-view.tsx", "src/features/fundamental/components/fundamental-actions.tsx", "src/features/fundamental/lib/analysis-request.ts", "src/features/fundamental/api/reports.ts", "src/shared/server/fundamental-analysis-config.ts", "src/shared/server/session-proxy.ts", "src/app/api/private/[...path]/route.ts"];
const fundamentalLint=["src/app/fundamental/page.tsx", "src/app/page.tsx", "src/app/reports/fundamental/[reportId]/page.tsx", "src/features/fundamental/components/analysis-request.tsx", "src/features/fundamental/components/fundamental-report-view.tsx", "src/features/fundamental/components/fundamental-actions.tsx", "src/features/fundamental/lib/analysis-request.ts", "src/features/fundamental/api/reports.ts", "src/shared/server/fundamental-analysis-config.ts", "src/shared/server/session-proxy.ts", "src/app/api/private/[...path]/route.ts", "tests/unit/fundamental/analysis-request.test.mjs", "tests/unit/bff/session-proxy.test.mjs", "tests/unit/config/ports.test.mjs", "scripts/check-local-ports.mjs"];
const analysisUnit=['unit/flow/analysis-request.test.mjs','unit/bff/session-proxy.test.mjs','unit/config/ports.test.mjs'];
export const flowReviewUnit=['unit/flow/report-display.test.mjs','unit/flow/report-deletion.test.mjs','tooling/safe-checks.test.mjs'];
export const flowReviewType=['src/features/flow/lib/report-display.ts','src/features/flow/lib/report-deletion.ts','src/features/flow/components/flow-report-view.tsx','src/features/flow/components/session-controls.tsx','src/app/reports/flow/[reportId]/page.tsx'];
export const flowReviewExact=['tests/fixtures/cf019-flow-display-cases.json',...flowReviewUnit.map(p=>'tests/'+p),'tests/integration/flow/report-browser-fixture.mjs',...flowReviewType];
export const reactProductionFiles=['react/cjs/react.production.js','react/cjs/react-jsx-runtime.production.js','react-dom/cjs/react-dom.production.js','react-dom/cjs/react-dom-client.production.js','scheduler/cjs/scheduler.production.js'];
export function reactRecords(dependency,sourceRoot=project){
 const lock=JSON.parse(readSource(sourceRoot,'package-lock.json').toString());
 return reactProductionFiles.map(relative=>{
  const name=relative.split('/')[0],filename=path.join(dependency,relative),metadata=fs.lstatSync(filename),manifest=JSON.parse(fs.readFileSync(path.join(dependency,name,'package.json'),'utf8'));
  if(fs.realpathSync(filename)!==filename||!metadata.isFile()||metadata.nlink!==1||manifest.version!==lock.packages['node_modules/'+name].version)throw Error('CF019 production dependency identity mismatch');
  return {relative,size:metadata.size,sha256:crypto.createHash('sha256').update(fs.readFileSync(filename)).digest('hex'),version:manifest.version};
 });
}
const http=['integration/bff/disabled-http.test.mjs','integration/bff/session-http.test.mjs','integration/bff/ports-http.test.mjs','integration/bff/synthetic-demo-http.test.mjs'];
const fixed=['tests/fixtures/cf005-observation-cases.json','src/features/flow/lib/observation-window.ts','package.json','package-lock.json','tsconfig.json','next.config.ts','postcss.config.mjs','eslint.config.mjs',
 ...flowReviewExact,...unit.map(p=>'tests/'+p),...http.map(p=>'tests/'+p),'tests/helpers/safe-http.mjs','scripts/safe-checks-guard.cjs','scripts/check-local-ports.mjs'];
const fresh=new Set(['scripts/safe-checks-guard.cjs','tests/helpers/safe-http.mjs','tests/tooling/safe-checks.test.mjs','tests/unit/flow/observation.test.mjs','tests/fixtures/cf005-observation-cases.json','src/features/flow/lib/observation-window.ts']);
for(const file of ["src/app/fundamental/page.tsx", "src/app/page.tsx", "src/app/reports/fundamental/[reportId]/page.tsx", "src/features/fundamental/components/analysis-request.tsx", "src/features/fundamental/components/fundamental-report-view.tsx", "src/features/fundamental/components/fundamental-actions.tsx", "src/features/fundamental/lib/analysis-request.ts", "src/features/fundamental/api/reports.ts", "src/shared/server/fundamental-analysis-config.ts", "src/shared/server/session-proxy.ts", "src/app/api/private/[...path]/route.ts", "tests/unit/fundamental/analysis-request.test.mjs", "tests/unit/bff/session-proxy.test.mjs", "tests/unit/config/ports.test.mjs", "scripts/check-local-ports.mjs"])fresh.add(file);
for(const file of ["src/shared/server/flow-demo-config.ts", "src/app/flow/demo/page.tsx", "src/features/flow/components/synthetic-demo.tsx", "src/features/flow/lib/synthetic-demo.ts", "tests/unit/flow/synthetic-demo.test.mjs", "tests/integration/bff/synthetic-demo-http.test.mjs"])fresh.add(file);
for(const file of ['src/shared/server/flow-analysis-config.ts','src/features/flow/components/analysis-request.tsx','src/features/flow/lib/analysis-request.ts','tests/unit/flow/analysis-request.test.mjs'])fresh.add(file);
const icons=new Set(['file.svg','globe.svg','next.svg','vercel.svg','window.svg'].map(p=>'public/'+p));
export const relocationSources=Object.freeze({
  "src/api/backend.ts": "src/shared/api/backend.ts",
  "src/components/ui/app-shell.tsx": "src/shared/ui/app-shell.tsx",
  "src/components/ui/section-card.tsx": "src/shared/ui/section-card.tsx",
  "src/components/ui/status-badge.tsx": "src/shared/ui/status-badge.tsx",
  "src/lib/bold-text.tsx": "src/shared/ui/bold-text.tsx",
  "src/lib/format.ts": "src/shared/lib/format.ts",
  "src/types/archive.ts": "src/shared/contracts/report.ts",
  "src/api/archive.ts": "src/features/archive/api/reports.ts",
  "src/api/flow-create.ts": "src/features/flow/api/create-report.ts",
  "src/api/flow.ts": "src/features/flow/api/reports.ts",
  "src/api/fundamental-create.ts": "src/features/fundamental/api/create-report.ts",
  "src/api/fundamental.ts": "src/features/fundamental/api/reports.ts",
  "src/api/industry-create.ts": "src/features/industry/api/create-report.ts",
  "src/api/industry.ts": "src/features/industry/api/reports.ts",
  "src/api/news-create.ts": "src/features/news/api/create-report.ts",
  "src/api/news.ts": "src/features/news/api/reports.ts",
  "src/api/supervisor.ts": "src/features/supervisor/api/analyze.ts",
  "src/api/technical-create.ts": "src/features/technical/api/create-report.ts",
  "src/api/technical.ts": "src/features/technical/api/reports.ts",
  "src/lib/archive-pagination.ts": "src/features/archive/lib/pagination.ts",
  "src/lib/disabled-feature.ts": "src/shared/server/disabled-feature.ts",
  "src/lib/report-links.ts": "src/features/archive/lib/report-links.ts",
  "src/lib/session-backend.ts": "src/shared/server/session-backend.ts",
  "src/lib/session-proxy.ts": "src/shared/server/session-proxy.ts",
  "src/lib/technical-chart.ts": "src/features/technical/lib/chart.ts",
  "src/lib/technical-labels.ts": "src/features/technical/lib/labels.ts",
  "src/types/news.ts": "src/features/news/model/types.ts",
  "src/types/supervisor.ts": "src/features/supervisor/model/types.ts",
  "src/types/technical.ts": "src/features/technical/model/types.ts",
  "docs/frontend_coding_guidelines.md": "docs/coding-guidelines.md",
  "tests/disabled-http.test.mjs": "tests/integration/bff/disabled-http.test.mjs",
  "tests/disabled-routes.test.mjs": "tests/unit/bff/disabled-routes.test.mjs",
  "tests/ports-http.test.mjs": "tests/integration/bff/ports-http.test.mjs",
  "tests/ports.test.mjs": "tests/unit/config/ports.test.mjs",
  "tests/safe-checks.test.mjs": "tests/tooling/safe-checks.test.mjs",
  "tests/session-http.test.mjs": "tests/integration/bff/session-http.test.mjs",
  "tests/session-proxy.test.mjs": "tests/unit/bff/session-proxy.test.mjs"
});
export function relocatedSource(p){return Object.hasOwn(relocationSources,p)?relocationSources[p]:p;}
const packageSHA='5dcc4949fad70a41d4c4fe5639f63931fcaf99accd3019a53052c00a4e697ef5';
let parentPublicPackageReads=0;
export function manifestIdentity(filename){
 const pieces=filename.split(path.sep).filter(Boolean),rows=[];
 for(let n=0;n<=pieces.length;n++){
  const p=path.sep+pieces.slice(0,n).join(path.sep),s=fs.lstatSync(p,{bigint:true});
  if(s.isSymbolicLink()||n===pieces.length&&(!s.isFile()||s.nlink!==1n)||n<pieces.length&&!s.isDirectory())throw Error('manifest identity rejected');
  rows.push({dev:String(s.dev),ino:String(s.ino),mode:String(s.mode),...(n===pieces.length?{size:String(s.size),mtime:String(s.mtimeNs),ctime:String(s.ctimeNs),nlink:String(s.nlink)}:{})});
 }
 return rows;
}
export function packageRecord(root,dependency,original,sourceIdentity,sourceRoot=project){
 const literal=path.join(sourceRoot,'package.json'),snapshot=path.join(root,'package.json');
 if(sourceRoot!==fs.realpathSync(sourceRoot)||fs.realpathSync(path.join(sourceRoot,'node_modules'))!==dependency)throw Error('unreviewed source/dependency relation');
 const snapshotIdentity=manifestIdentity(snapshot),copy=readSource(root,'package.json');
 if(original.length!==707||!original.equals(copy)||crypto.createHash('sha256').update(original).digest('hex')!==packageSHA||JSON.stringify(sourceIdentity)!==JSON.stringify(manifestIdentity(literal))||JSON.stringify(snapshotIdentity)!==JSON.stringify(manifestIdentity(snapshot)))throw Error('reviewed package snapshot drift');
 return {sourceRoot,literal,snapshot,sourceIdentity,snapshotIdentity,length:707,sha256:packageSHA};
}
export function recheckPackage(record,root,dependency){
 // v1.6 6-B.7: parent only, using the already approved public source-copy procedure.
 // This is never called by the worker; no source FD is inherited.
 const before=manifestIdentity(record.literal);
 if(JSON.stringify(before)!==JSON.stringify(record.sourceIdentity)||JSON.stringify(manifestIdentity(record.snapshot))!==JSON.stringify(record.snapshotIdentity))throw Error('package identity drift before reread');
 const bytes=readSource(record.sourceRoot,'package.json');
 if(JSON.stringify(packageRecord(root,dependency,bytes,before,record.sourceRoot))!==JSON.stringify(record))throw Error('package identity/hash drift; result rejected');
}
export async function checkedCommand({record,root,dependency,argv,env,timeout,children,prepare=()=>{},invoke=command}){
 recheckPackage(record,root,dependency);
 let output,failure;
 try{prepare();output=await invoke(argv,{root,env,timeout,children});}catch(error){failure=error;}
 try{recheckPackage(record,root,dependency);}catch(error){if(failure)throw new AggregateError([failure,error],'command and package postcheck failed');throw error;}
 if(failure)throw failure;
 return output;
}
// Exact tracked BFF source, not a data/private-directory grant. Index/identity checks still apply.
const privateRouteSource='src/app/api/private/[...path]/route.ts';
for(const name of flowReviewExact)fresh.add(name);
export function privatePath(p){if(p===privateRouteSource)return false;const blocked=new Set(['private','secret','secrets','key','keys','credential','credentials','dump','dumps','backup','backups','log','logs']);return p.split('/').some(part=>blocked.has(part.toLowerCase())||part.toLowerCase().startsWith('.env')||part.toLowerCase().startsWith('credentials')||part.toLowerCase().split('.').slice(1).some(s=>['key','pem','p12','sql','dump','bak','backup','log'].includes(s)));}
export function sourceAllowed(p){return !privatePath(p)&&(fixed.includes(p)||icons.has(p)||p.startsWith('src/')&&/\.(ts|tsx|css|ico)$/.test(p));}
export function readSource(root,relative){
 if(privatePath(relative)||path.isAbsolute(relative)||relative.split('/').includes('..')||relative.split('/').some(p=>p.startsWith('.env')||p.toLowerCase().startsWith('credentials'))||/\.(key|pem|p12|sql|log|backup|dump)$/.test(relative))throw Error('unsafe source name');
 const parts=relative.split('/').map((_,i,a)=>path.join(root,...a.slice(0,i+1)));
 const identities=parts.map(p=>fs.lstatSync(p));
 if(identities.some(s=>s.isSymbolicLink())||!identities.at(-1).isFile()||identities.at(-1).nlink!==1)throw Error('unsafe source identity');
 const fd=fs.openSync(path.join(root,relative),fs.constants.O_RDONLY|fs.constants.O_NOFOLLOW|fs.constants.O_NONBLOCK);
 try{
  const s=fs.fstatSync(fd),before=identities.at(-1);
  if(!s.isFile()||s.nlink!==1||s.ino!==before.ino||s.dev!==before.dev)throw Error('source changed before open');
  if(root===project&&relative==='package.json')parentPublicPackageReads++;
  const data=fs.readFileSync(fd);
  for(let i=0;i<parts.length;i++){const now=fs.lstatSync(parts[i]),was=identities[i];if(now.ino!==was.ino||now.dev!==was.dev||now.mtimeMs!==was.mtimeMs||now.size!==was.size)throw Error('source changed while copying');}
  return data;
 }finally{fs.closeSync(fd);}
}
export function ownedRoot(parentDirectory='/tmp'){
 const root=fs.realpathSync(fs.mkdtempSync(path.join(parentDirectory,'st001-3b-next-')));fs.chmodSync(root,0o700);
 const identity=fs.lstatSync(root),parent=fs.statSync(path.dirname(root)),nonce=crypto.randomBytes(24).toString('hex');
 fs.writeFileSync(path.join(root,'.owner'),nonce,{mode:0o600});
 return {root,nonce,close(){const s=fs.lstatSync(root),p=fs.statSync(path.dirname(root));if(s.isSymbolicLink()||s.dev!==identity.dev||s.ino!==identity.ino||p.dev!==parent.dev||p.ino!==parent.ino||fs.lstatSync(path.join(root,'.owner')).isSymbolicLink()||fs.readFileSync(path.join(root,'.owner'),'utf8')!==nonce)throw Error('cleanup ownership mismatch; retained');fs.rmSync(root,{recursive:true});if(fs.existsSync(root))throw Error('cleanup failed');}};
}
function trusted(p){const real=fs.realpathSync(p),s=fs.statSync(real);if(![0,process.getuid()].includes(s.uid)||s.mode&0o022)throw Error('untrusted dependency metadata');return real;}
function environment(root,extra={}){return {LANG:'en_US.UTF-8',TZ:'UTC',HOME:root,TMPDIR:root,PATH:'/usr/bin:/bin',NEXT_TELEMETRY_DISABLED:'1',NO_UPDATE_NOTIFIER:'1',OPENSSL_CONF:'/dev/null',...extra};}
export async function waitExit(child,timeout){
 if(child.exitCode!==null||child.signalCode!==null)return;
 await Promise.race([new Promise((resolve,reject)=>{child.once('exit',resolve);child.once('error',reject);}),new Promise((_,reject)=>setTimeout(()=>reject(Error('child exit timeout')),timeout).unref())]);
}
export async function retireGroup(ops){
 // Direct leader exit is NOT equivalent to owned group exit.
 if(ops.exists()){
  if(!ops.owned())throw Error('group ownership mismatch; not signalling');
  ops.signal('SIGTERM');
  if(!await ops.waitGroup(3000)){
   if(!ops.owned())throw Error('group identity changed before KILL');
   ops.signal('SIGKILL');
   if(!await ops.waitGroup(3000))throw Error('owned group survived KILL');
  }
 }
 await ops.waitDirect();
}
function groupExists(group){try{process.kill(-group,0);return true;}catch(error){if(error.code==='ESRCH')return false;throw error;}}
export async function stopChild(child){
 if(!child.pid)return;
 const root=child.st001OwnedRoot;
 if(!root)throw Error('missing owned child receipt');
 const owned=()=>{
  if(!groupExists(child.pid))return true;
  const members=execFileSync('/bin/ps',['-o','pid=','-g',String(child.pid)],{env:environment(root)}).toString().trim().split(/\s+/);
  if(!members.length||members.some(pid=>!/^\d+$/.test(pid)))return false;
  return members.every(pid=>{
   const cwd=execFileSync('/usr/sbin/lsof',['-a','-p',pid,'-d','cwd','-Fn'],{env:environment(root),timeout:2000}).toString().split('\n').find(line=>line.startsWith('n'))?.slice(1);
   return cwd===root||cwd?.startsWith(root+path.sep);
  });
 };
 await retireGroup({exists:()=>groupExists(child.pid),owned,signal:signal=>process.kill(-child.pid,signal),
  async waitGroup(milliseconds){for(let n=0;n<milliseconds/50;n++){if(!groupExists(child.pid))return true;await new Promise(resolve=>setTimeout(resolve,50));}return !groupExists(child.pid);},
  waitDirect:()=>waitExit(child,3000)});
}
export async function abortOwned(children,retire){
 const errors=[];
 await Promise.all([...children].map(async child=>{try{await retire(child);children.delete(child);}catch(error){errors.push(error);}}));
 if(errors.length)throw new AggregateError(errors,'Owned group cleanup incomplete; root retained');
}
export async function command(argv,{root,env,timeout=120000,children=new Set(),launch=spawn,retire=stopChild,wait=waitExit}){
 let child;
 try{
  child=launch(argv[0],argv.slice(1),{cwd:root,env,detached:true,stdio:['ignore','pipe','pipe']});
  child.st001OwnedRoot=root;
  children.add(child); // register before readiness and before any await
  let output='';
  for(const stream of [child.stdout,child.stderr])stream.on('data',chunk=>{output=(output+chunk).slice(-200000);});
  await wait(child,timeout);
  if(child.exitCode!==0){
   // Keep the journal/aggregate as evidence; its long exit JSON must not mask
   // the bounded stderr/TAP failure in the command's human-facing summary.
   const failure=output.replace(/^ST001_SNAPSHOT [^\n]*(?:\n|$)/gm,'').slice(-4000);
   throw Error('check child failed '+String(child.exitCode)+': '+failure);
  }
  return output;
 }finally{if(child){await retire(child);children.delete(child);}}
}
// Seatbelt uses the special host token localhost for loopback (not IP text).
// The existing JS endpoint/DNS guard still pins 127.0.0.1 / ::1 and exact ports.
export function loopbackRules(ports){
 if(!Array.isArray(ports)||ports.length>2||new Set(ports).size!==ports.length||ports.some(port=>!Number.isInteger(port)||port<1||port>65535))throw Error('invalid exact loopback ports');
 return ports.flatMap(port=>[`(allow network-inbound (local tcp "localhost:${port}"))`,`(allow network-outbound (remote tcp "localhost:${port}"))`]);
}
function policy(root,dependency,node,ports=[]){
 const q=JSON.stringify;
 const reads=['/System','/usr/lib','/private/var/db/dyld',root,dependency,path.dirname(path.dirname(node))];
 // Exact transitive Homebrew native library roots: no /opt/homebrew or home-wide grant.
 for(const name of ['libuv','brotli','c-ares','libnghttp2','openssl@3','icu4c'])reads.push(trusted('/opt/homebrew/opt/'+name+'/lib'));
 return ['(version 1)','(deny default)','(allow file-read* file-test-existence (literal "/"))','(allow file-read-metadata)','(allow sysctl-read)','(allow mach-lookup)','(allow process-fork)','(allow process-info*)','(allow signal (target children))',
 `(allow process-exec (literal ${q(node)}) (literal "/bin/cat") (literal "/usr/bin/true") (literal "/bin/ps") (literal "/usr/sbin/lsof"))`,
 '(allow file-read-data '+reads.map(p=>`(subpath ${q(p)})`).join(' ')+' (literal "/dev/null") (literal "/dev/urandom") (literal "/bin/cat") (literal "/usr/bin/true") (literal "/bin/ps") (literal "/usr/sbin/lsof"))',
 `(allow file-write* (subpath ${q(root)}) (literal "/dev/null"))`,
 ...loopbackRules(ports)].join('\n');
}
export function validNativeProbe(stage,result,deniedPath){
 if(result.signal!==null||!Number.isInteger(result.status)||result.status<0)return false;
 if(stage==='true'||stage==='allowed')return result.status===0&&result.stdout===(stage==='true'?'':'SYNTHETIC-ALLOWED\n')&&result.stderr==='';
 return stage==='denied'&&result.status===1&&result.stdout===''&&[`cat: ${deniedPath}: Operation not permitted\n`,`cat: ${deniedPath}: Permission denied\n`].includes(result.stderr);
}
export async function verifyNativeSequence(stages,execute,deniedPath){
 for(const [stage,command] of stages){
  const result=await execute(command);
  if(!validNativeProbe(stage,result,deniedPath))throw Error('OS canary '+stage+' failed; not a protection success');
 }
}
async function nativeResult(argv,{root,children}){
 let child;
 try{
  child=spawn(argv[0],argv.slice(1),{cwd:root,env:environment(root),detached:true,stdio:['ignore','pipe','pipe']});
  child.st001OwnedRoot=root;children.add(child);
  let stdout='',stderr='',exceeded=false;
  child.stdout.on('data',data=>{stdout+=data;exceeded=exceeded||stdout.length>200000;stdout=stdout.slice(-200000);});
  child.stderr.on('data',data=>{stderr+=data;exceeded=exceeded||stderr.length>200000;stderr=stderr.slice(-200000);});
  // close, not only exit: both pipe streams must have finished before comparison.
  await new Promise((resolve,reject)=>{
   const timer=setTimeout(()=>reject(Error('native probe timeout')),10000);timer.unref();
   child.once('close',()=>{clearTimeout(timer);resolve();});
   child.once('error',error=>{clearTimeout(timer);reject(error);});
  });
  if(exceeded)throw Error('native probe output limit');
  return {status:child.exitCode,signal:child.signalCode,stdout,stderr};
 }finally{if(child){await stopChild(child);children.delete(child);}}
}
async function osProof(owned,dependency,node,children){
 const root=owned.root,inside=path.join(root,'inside-canary'),outside=path.join('/private/tmp','st001-denied-'+crypto.randomBytes(24).toString('hex'));
 const file=path.join(root,'policy.sb');fs.writeFileSync(file,policy(root,dependency,node));fs.writeFileSync(inside,'SYNTHETIC-ALLOWED\n');fs.writeFileSync(outside,'SYNTHETIC-DENIED\n',{flag:'wx',mode:0o600});
 try{
  await verifyNativeSequence([['true',['/usr/bin/true']],['allowed',['/bin/cat',inside]],['denied',['/bin/cat',outside]]],
   command=>nativeResult(['/usr/bin/sandbox-exec','-f',file,...command],{root,children}),outside);
 }finally{fs.unlinkSync(outside);fs.unlinkSync(inside);}
}
function copyProject(root,dependency){
 const records=execFileSync('/usr/bin/git',['ls-files','--stage','-z','--','frontend'],{cwd:repo,env:{PATH:'/usr/bin:/bin',LANG:'en_US.UTF-8'}}).toString().split('\0').filter(Boolean);
 const selected=new Set();
 for(const row of records){const [meta,full]=row.split('\t'),p=relocatedSource(full.slice('frontend/'.length));if(!sourceAllowed(p))continue;if(!meta.startsWith('100644 ')||!meta.endsWith(' 0'))throw Error('unsupported index source');selected.add(p);}
 for(const p of fresh)selected.add(p);
 for(const p of fixed)if(!selected.has(p))throw Error('required copy source missing');
 const hashes={};let packageBytes,packageSourceIdentity;
 for(const p of selected){
  const before=p==='package.json'?manifestIdentity(path.join(project,p)):undefined;
  const bytes=readSource(project,p),target=path.join(root,p);fs.mkdirSync(path.dirname(target),{recursive:true});fs.writeFileSync(target,bytes);hashes[p]=crypto.createHash('sha256').update(bytes).digest('hex');
  if(p==='package.json'){packageBytes=bytes;packageSourceIdentity=before;}
 }
 for(const p of selected)if(hashes[p]!==crypto.createHash('sha256').update(readSource(project,p)).digest('hex'))throw Error('source changed after copy');
 fs.symlinkSync(dependency,path.join(root,'node_modules'),'dir');
 fs.writeFileSync(path.join(root,'source-hashes.json'),JSON.stringify(hashes));
 return {packageSnapshot:packageRecord(root,dependency,packageBytes,packageSourceIdentity),copySources:[...selected]};
}
export function validateTestOutput(output){
 const count=output.match(/^# tests ([1-9][0-9]*)$/m);
 if(!count||/^# (?:fail|cancelled|skipped|skip|todo) [1-9][0-9]*$/m.test(output))throw Error('zero collection or unexpected failure/skip/cancel/todo');
 return Number(count[1]);
}
export function aggregateDiagnostics(records,run,allowedLabels){
 const combined=new Map();
 for(let worker=0;worker<records.length;worker++){
  const entries=records[worker].diagnostics??[];
  if(!Array.isArray(entries)||entries.length>256)throw Error('diagnostic aggregate budget');
  for(const e of entries){
   const fields=['schema','run','workerRole','workload','api','access','callerFamily','callerId','label','targetId','lexicalId','role','privateNameMatch','knownCopy','count'];
   if(Object.keys(e).some(k=>!fields.includes(k))||e.schema!==1||e.run!==run||!['entry-worker','next-worker'].includes(e.workerRole)||!['self-test','unit','build','local-http','type','lint','all'].includes(e.workload)||typeof e.api!=='string'||!/^(?:promises\.)?[A-Za-z]{1,24}$/.test(e.api)||!['read','write'].includes(e.access)||!['telemetry-container-detection','webpack-file-hash','other'].includes(e.callerFamily)||!['owned-root','verified-dependency','reviewed-runtime','original-project','original-repo','outside','unknown'].includes(e.role)||typeof e.privateNameMatch!=='boolean'||typeof e.knownCopy!=='boolean'||!Number.isSafeInteger(e.count)||e.count<1||e.count>1000000||e.label!==null&&!allowedLabels.has(e.label)||!['callerId','targetId'].every(k=>typeof e[k]==='string'&&/^[a-f0-9]{64}$/.test(e[k]))||e.lexicalId!==undefined&&!/^[a-f0-9]{64}$/.test(e.lexicalId))throw Error('invalid diagnostic event');
   const {count,...identity}=e,token=JSON.stringify(identity);
   if(!combined.has(token)&&combined.size>=512)throw Error('diagnostic aggregate budget');
   const item=combined.get(token)??{...identity,count:0,workers:new Set()};item.count+=count;item.workers.add(worker);combined.set(token,item);
  }
 }
 return [...combined.values()].map(e=>({...e,workers:e.workers.size}));
}
export function reportObservations(root,diagnosticContext){
 const totals={workers:0,exitRecords:0,partialWorkers:0,observedOriginalRawDispatches:0,observedOriginalDenied:0,deniedTotal:0,expectedNegatives:0,diagnosticFailures:0,hits:{readFile:0,readFileSync:0,promisesReadFile:0},violations:{},scope:'instrumented-js-fs-journals-only',native:'not-observed'};
 const records=[];
 for(const name of fs.readdirSync(root).filter(name=>/^\.snapshot-ledger-[0-9]+-[a-f0-9]{16}\.jsonl$/.test(name))){
  if(fs.lstatSync(path.join(root,name)).size>2000000)throw Error('worker observation journal too large');
  const rows=readSource(root,name).toString().trim().split('\n').map(row=>JSON.parse(row));
  const last=rows.at(-1);if(!last||last.scope!=='instrumented-js-fs-consumer-dispatch-only')throw Error('invalid worker observation journal');
  records.push(last);totals.diagnosticFailures+=last.diagnosticFailures??0;
  totals.workers++;if(last.event==='exit')totals.exitRecords++;else totals.partialWorkers++;
  totals.observedOriginalRawDispatches+=last.rawOriginalDispatches;totals.observedOriginalDenied+=last.rawOriginalDenied;
  totals.deniedTotal+=last.deniedTotal;totals.expectedNegatives+=last.expectedNegatives;
  for(const key of Object.keys(totals.hits))totals.hits[key]+=last.snapshot.hits[key];
  for(const kind of last.violations)totals.violations[kind]=(totals.violations[kind]??0)+1;
 }
 if(diagnosticContext){
  const labels=new Set(['telemetry-container-probe:cgroup','public-bff-private-route',...['package.json','package-lock.json','tsconfig.json','next.config.ts','postcss.config.mjs','eslint.config.mjs'].map(n=>'original-project-metadata:'+n),...diagnosticContext.copySources.filter(n=>!privatePath(n)).map(n=>'copied-source:'+n)]);
  totals.targets=aggregateDiagnostics(records,diagnosticContext.run,labels);
  totals.distinctTargets=new Set(totals.targets.map(e=>e.targetId)).size;
 }
 console.log('ST001_WORKER_OBSERVATIONS '+JSON.stringify(totals));
 if(!totals.workers||totals.observedOriginalRawDispatches||Object.keys(totals.violations).length||totals.deniedTotal!==totals.expectedNegatives||totals.diagnosticFailures)throw Error('worker observation records show unexpected denial/raw dispatch');
 return totals;
}
// Fixed readiness wait: preserve an early protected command failure instead of
// replacing its bounded stderr/exit evidence with a later generic proof error.
export async function browserReadiness(task,readProof,pause=()=>new Promise(resolve=>setTimeout(resolve,100))){
 const settled=task.then(output=>({output}),error=>({error}));
 for(let i=0;i<100;i++){
  const proof=readProof();if(proof)return proof;
  const result=await Promise.race([settled,pause()]);
  if(result){
   if(Object.hasOwn(result,'error'))throw result.error;
   throw Error('CF019 worker exited before readiness: '+String(result.output).slice(-2000));
  }
 }
 throw Error('CF019 worker readiness timeout (10s; no proof)');
}
// Stop only registered owned children, then await command finally + package
// postcheck before the enclosing controller may remove its source-copy root.
export async function stopAndSettleBrowserTask(task,stop){
 let stopFailure;try{await stop();}catch(error){stopFailure=error;}
 const settled=await task.then(()=>({status:'fulfilled'}),error=>({status:'rejected',error}));
 if(stopFailure)throw stopFailure;
 return settled;
}
async function execute(selected){
 const flowReviewOnly=selected.length===1&&selected[0].startsWith('flow-review-');
 const browserOnly=flowReviewOnly&&selected[0]==='flow-review-browser';
 if(flowReviewOnly)selected=[selected[0]==='flow-review-type'?'type':selected[0]==='flow-review-lint'?'lint':'unit'];
 const fundamentalOnly=selected.length===1&&selected[0].startsWith('fundamental-');
 if(fundamentalOnly)selected=[selected[0]==='fundamental-unit'?'unit':selected[0]==='fundamental-type'?'type':'lint'];
 const analysisOnly=selected.length===1&&selected[0].startsWith('analysis-');
 if(analysisOnly)selected=[selected[0]==='analysis-unit'?'unit':selected[0]==='analysis-type'?'type':'lint'];
 if(Object.keys(process.env).some(k=>!['LANG','TZ','__CF_USER_TEXT_ENCODING','OPENSSL_CONF'].includes(k)))throw Error('use documented env -i launch; startup injection cannot be undone');
 if(process.env.OPENSSL_CONF!=='/dev/null')throw Error('clean launch must pin OPENSSL_CONF=/dev/null before Node native startup');
 const node=trusted(process.execPath),dependency=trusted(path.join(project,'node_modules'));
 for(const f of ['next/dist/bin/next','typescript/bin/tsc','eslint/bin/eslint.js'])trusted(path.join(dependency,f));
 let aborted=false,taskError;const abortErrors=[],stops=[];
 const owned=ownedRoot(),children=new Set();let diagnosticContext;
 const interrupt=()=>{aborted=true;stops.push(abortOwned(children,stopChild).catch(error=>{abortErrors.push(error);}));};
 const deadline=setTimeout(interrupt,1800000);process.on('SIGINT',interrupt);process.on('SIGTERM',interrupt);
 try{
  await osProof(owned,dependency,node,children); // MUST pass before any source copy/app worker
  const root=owned.root,{packageSnapshot,copySources}=copyProject(root,dependency);
  // Production-only readiness endpoint in this owned copy, never in original src.
  const route=path.join(root,'src/app/__st001_ready/route.ts');fs.mkdirSync(path.dirname(route),{recursive:true});
  fs.writeFileSync(route,`export const dynamic='force-dynamic';export function GET(){return Response.json({nonce:${JSON.stringify(owned.nonce)},pid:process.pid,cwd:process.cwd()});}`);
  const capfile=path.join(root,'capability.json'),guard=path.join(root,'scripts/safe-checks-guard.cjs');
  diagnosticContext={key:crypto.randomBytes(32).toString('hex'),run:crypto.randomBytes(12).toString('hex'),copySources};
  const cap={root,dependency,runtime:[path.dirname(path.dirname(node)),'/System','/usr/lib'],ports:[],lifetime:browserOnly?600:1800,nonce:owned.nonce,packageSnapshot,diagnostics:diagnosticContext,workload:selected.length===1?selected[0]:'all'};
  fs.writeFileSync(capfile,JSON.stringify(cap),{mode:0o600});
  const env=environment(root,{NODE_OPTIONS:'--require='+guard,ST001_SAFE_CAP:capfile,NODE_ENV:'production'});
  const profile=path.join(root,'policy.sb');
  const run=async(args,timeout)=>{if(aborted)throw Error('controller interrupted/expired');return checkedCommand({record:packageSnapshot,root,dependency,argv:['/usr/bin/sandbox-exec','-f',profile,node,...args],env,timeout,children,prepare(){cap.lifetime=Math.floor(timeout/1000);fs.writeFileSync(capfile,JSON.stringify(cap));}});};
  if(selected.includes('self-test')){const output=await run(['--test-reporter=tap','tests/tooling/safe-checks.test.mjs'],120000);validateTestOutput(output);console.log(output);}
  if(selected.includes('unit')&&!browserOnly)for(const file of (flowReviewOnly?flowReviewUnit:fundamentalOnly?fundamentalUnit:analysisOnly?analysisUnit:unit)){const output=await run(['--test-reporter=tap','tests/'+file],120000);validateTestOutput(output);console.log(output);}
  if(browserOnly){
   const {reservePair}=await import('../tests/helpers/safe-http.mjs');const reservations=await reservePair();let task,browserFailure;
   try{
    cap.ports=reservations.ports;cap.reactProduction=reactRecords(dependency);fs.writeFileSync(capfile,JSON.stringify(cap));fs.writeFileSync(profile,policy(root,dependency,node,cap.ports));await reservations.close();
    task=run(['--test-reporter=tap','tests/integration/flow/report-browser-fixture.mjs'],600000);
    const proof=await browserReadiness(task,()=>{const file=path.join(root,'cf019-ready.json');return fs.existsSync(file)?JSON.parse(fs.readFileSync(file,'utf8')):null;});
    if(!proof||proof.nonce!==owned.nonce||proof.cwd!==root||proof.port!==cap.ports[0]||![...children].some(child=>child.pid===proof.pid&&child.st001OwnedRoot===root))throw Error('CF019 worker readiness ownership mismatch');
    const listener=execFileSync('/usr/sbin/lsof',['-nP','-a','-p',String(proof.pid),'-iTCP:'+proof.port,'-sTCP:LISTEN','-Fpn'],{env:{PATH:'/usr/bin:/bin',LANG:'en_US.UTF-8'}}).toString().trim().split('\n');
    const cwd=execFileSync('/usr/sbin/lsof',['-a','-p',String(proof.pid),'-d','cwd','-Fn'],{env:{PATH:'/usr/bin:/bin',LANG:'en_US.UTF-8'}}).toString().trim().split('\n');
    if(!listener.includes('p'+proof.pid)||!listener.includes('n127.0.0.1:'+proof.port)||!cwd.includes('n'+root))throw Error('CF019 listener/cwd identity mismatch');
    console.log('CF019_OWNED_READY '+JSON.stringify({port:proof.port,nonce:owned.nonce,pid:proof.pid,cwd:root}));
    console.log(await task);
   }catch(error){browserFailure=error;throw error;}finally{
    try{await reservations.close();}finally{
     if(task){
      const settled=await stopAndSettleBrowserTask(task,()=>abortOwned(children,stopChild));
      if(settled.status==='rejected'){
       if(!browserFailure)throw settled.error;
       if(settled.error!==browserFailure)console.error('CF019_TASK_SETTLED_AFTER_FAILURE '+String(settled.error?.message??'command failed').slice(-4000));
      }
     }
     if(JSON.stringify(cap.reactProduction)!==JSON.stringify(reactRecords(dependency)))throw Error('CF019 production dependency postcheck drift');
    }
   }
  }
  if(selected.includes('build')||selected.includes('local-http'))console.log(await run(['node_modules/next/dist/bin/next','build','--webpack'],900000));
  if(selected.includes('local-http')){
   // Dynamic ports are reserved in the parent helper before profile generation.
   const {reservePair}=await import('../tests/helpers/safe-http.mjs');
   for(const file of http){
    const reservations=await reservePair(file==='integration/bff/ports-http.test.mjs');
    try{cap.ports=reservations.ports;fs.writeFileSync(capfile,JSON.stringify(cap));fs.writeFileSync(profile,policy(root,dependency,node,cap.ports));await reservations.close();const output=await run(['--test-reporter=tap','tests/'+file],120000);validateTestOutput(output);console.log(output);}
    finally{await reservations.close();}
   }
   cap.ports=[];fs.writeFileSync(capfile,JSON.stringify(cap));fs.writeFileSync(profile,policy(root,dependency,node));
  }
  if(selected.includes('type')){
   // Installed Next writeAppTypeDeclarations.js uses these exact standard references.
   // The owned copy has no ignored next-env file; this adds declarations, never any/stubs.
   fs.writeFileSync(path.join(root,'next-env.d.ts'),'/// <reference types=\"next\" />\n/// <reference types=\"next/image-types/global\" />\n');
   if(flowReviewOnly)fs.writeFileSync(path.join(root,'tsconfig.cf019.json'),JSON.stringify({extends:'./tsconfig.json',include:['next-env.d.ts',...flowReviewType]}));
   if(fundamentalOnly)fs.writeFileSync(path.join(root,'tsconfig.cf015.json'),JSON.stringify({extends:'./tsconfig.json',include:['next-env.d.ts',...fundamentalType]}));
   if(analysisOnly)fs.writeFileSync(path.join(root,'tsconfig.cf012.json'),JSON.stringify({extends:'./tsconfig.json',include:['next-env.d.ts','src/shared/server/flow-analysis-config.ts','src/features/flow/lib/analysis-request.ts','src/features/flow/components/analysis-request.tsx','src/app/research/page.tsx','src/app/page.tsx','src/shared/server/session-proxy.ts','src/app/api/private/[...path]/route.ts']}));
   console.log(await run(['node_modules/typescript/bin/tsc','--noEmit','--incremental','false',...(flowReviewOnly?['-p','tsconfig.cf019.json']:fundamentalOnly?['-p','tsconfig.cf015.json']:analysisOnly?['-p','tsconfig.cf012.json']:[])],180000));
  }
  if(selected.includes('lint')&&flowReviewOnly){
   const report=path.join(root,'cf019-eslint.json');
   try{console.log(await run(['node_modules/eslint/bin/eslint.js','--no-ignore','--format','json','--output-file',report,...flowReviewType,...flowReviewUnit.map(p=>'tests/'+p),'tests/integration/flow/report-browser-fixture.mjs','scripts/check-local-ports.mjs'],180000));}
   finally{if(fs.existsSync(report)){const findings=JSON.parse(fs.readFileSync(report,'utf8')).flatMap(file=>file.messages.map(m=>({file:path.relative(root,file.filePath),line:m.line,rule:m.ruleId,severity:m.severity,message:m.message.split('\n')[0]})));console.log('CF019_LINT '+JSON.stringify(findings));}}
  }
  if(selected.includes('lint')&&!flowReviewOnly)console.log(await run(['node_modules/eslint/bin/eslint.js','--no-ignore',
   ...(flowReviewOnly?[...flowReviewType,...flowReviewUnit.map(p=>'tests/'+p),'tests/integration/flow/report-browser-fixture.mjs','scripts/check-local-ports.mjs']:fundamentalOnly?fundamentalLint:analysisOnly?['src/shared/server/flow-analysis-config.ts','src/features/flow/lib/analysis-request.ts','src/features/flow/components/analysis-request.tsx','src/app/research/page.tsx','src/app/page.tsx','src/shared/server/session-proxy.ts','src/app/api/private/[...path]/route.ts','tests/unit/flow/analysis-request.test.mjs','tests/unit/bff/session-proxy.test.mjs','tests/unit/config/ports.test.mjs','scripts/check-local-ports.mjs']:Object.values(relocationSources).filter(p=>/\.(ts|tsx)$/.test(p))),
   ...(flowReviewOnly||analysisOnly||fundamentalOnly?[]:[ 'src/features/technical/components/indicator-card.tsx',
   'src/shared/server/flow-demo-config.ts','src/app/flow/demo/page.tsx','src/features/flow/components/synthetic-demo.tsx','src/features/flow/lib/synthetic-demo.ts','src/app/api/private/[...path]/route.ts','src/proxy.ts','tests/unit/flow/synthetic-demo.test.mjs',
   'src/features/flow/lib/observation-window.ts','src/features/flow/components/flow-report-view.tsx','tests/unit/flow/observation.test.mjs',
   'src/shared/server/session-backend.ts','src/shared/server/session-proxy.ts','src/features/archive/lib/pagination.ts','src/app/page.tsx','src/app/reports/flow/[reportId]/page.tsx','src/features/flow/components/session-controls.tsx','src/shared/api/backend.ts',
   'tests/unit/config/ports.test.mjs',...http.map(p=>'tests/'+p),'tests/tooling/safe-checks.test.mjs','tests/helpers/safe-http.mjs','scripts/check-local-ports.mjs','scripts/safe-checks-guard.cjs'])],180000));
 }catch(error){taskError=error;throw error;}finally{
  clearTimeout(deadline);process.off('SIGINT',interrupt);process.off('SIGTERM',interrupt);
  await Promise.all(stops);
  // Every group gets a cleanup attempt; failed receipts retain the owned root.
  await abortOwned(children,stopChild);
  let observationError;try{reportObservations(owned.root,diagnosticContext);}catch(error){observationError=error;}
  owned.close();
  if(abortErrors.length)throw new AggregateError(abortErrors,'Interrupt cleanup failed');
  console.log('Owned temporary root removed; existing resources unchanged');
  console.log('ST001_PARENT_PUBLIC_PACKAGE_READS '+parentPublicPackageReads+' (approved source-copy/pre-post validation; separate from worker)');
  if(observationError&&!taskError)throw observationError;
 }
}
export async function main(args=process.argv.slice(2)){
 if(args.length===1&&['--help','list'].includes(args[0])){console.log('Modes: '+modes.join(', ')+'; default: all. env -i absolute Node required. OS preflight is mandatory.');return 0;}
 if(args.length>1||args.length===1&&!modes.includes(args[0])){console.error('Unsupported mode/extra args');return 2;}
 try{await execute(args.length?args:modes);return 0;}catch(error){console.error('SAFE_CHECK_BLOCKED: '+error.message);return 78;}
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url))process.exitCode=await main();
