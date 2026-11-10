// Actual production chart fixture; import alone performs no reads or server work.
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import crypto from 'node:crypto';
import vm from 'node:vm';
import {pathToFileURL} from 'node:url';
import ts from 'typescript';
import {reactProductionFiles,chartProductionFiles} from '../../../scripts/check-local-ports.mjs';
import {createFixtureTerminal,terminalAction,browserNotExecuted} from '../../helpers/supervisor-fixture.mjs';

const moduleNames=['react','react/jsx-runtime','react-dom','react-dom/client','scheduler','recharts','lucide-react','react-is','Boundary','../lib/strict-boundary-read','./boundary-preview','./technical-chart-panel','@/features/technical/lib/chart','@/shared/lib/format'];
export function fixtureTarget(target){
 if(typeof target!=='string'||target.length>2048||!target.startsWith('/')||target.startsWith('//')||/[?%#\\\x00-\x20\x7f]/.test(target)||target.split('/').some(p=>p==='.'||p==='..'))return {status:422,kind:'invalid'};
 const routes={'/technical-preview':'html','/bundle.js':'bundle','/fixture.css':'css','/fixture-finish':'finish'};
 return Object.hasOwn(routes,target)?{status:200,kind:routes[target]}:{status:404,kind:'missing'};
}
export function fixtureCases(fixture){
 const clone=value=>structuredClone(value),A={response:clone(fixture.response),expected:clone(fixture.expected)},B=clone(A);
 B.expected.request.request_id='10000000-0000-4000-8000-000000000001';B.expected.request.trace_id='10000000-0000-4000-8000-000000000002';
 for(const [i,key] of ['analysis_id','admission_request_id','attempt_id','report_id'].entries())B.expected.request.data.context[key]='10000000-0000-4000-8000-'+String(i+3).padStart(12,'0');
 B.response.request_id=B.expected.request.request_id;B.response.trace_id=B.expected.request.trace_id;
 B.response.data.result.request_id=B.response.request_id;B.response.data.result.trace_id=B.response.trace_id;
 B.response.data.request_snapshot=clone(B.expected.request.data);
 // Precomputed from this fixed string-only request using Python canonical JSON.
 B.expected.request_sha256='757798a2ebbb1b770aea0f1602259601d12f50f5e9f04ff1e382618e925a9fe6';B.response.data.request_sha256=B.expected.request_sha256;
 const empty=clone(A),missing=clone(A),error=clone(A),invalid=clone(A);
 for(const c of empty.response.data.result.charts)c.chart_data.candles=[];
 delete missing.response.data.result.charts;
 for(const [item,status] of [[empty,'empty'],[missing,'not_provided']]){
  item.response.data.coverage.available_periods=[];
  for(const row of item.response.data.coverage.periods)Object.assign(row,{start:null,end:null,count:0,status});
 }
 error.response.data=null;error.response.error={code:'BUSY',message:'Technical boundary unavailable'};
 invalid.response.data.result.charts[0].chart_data.candles[0].open='invalid';
 return {A,B,empty,missing,error,invalid};
}
export function moduleProgram(registry){
 if(!registry||Object.keys(registry).some(id=>!moduleNames.includes(id))||Object.values(registry).some(s=>typeof s!=='string'))throw Error('CF033 registry invalid');
 return `(function(){const modules={${Object.entries(registry).map(([id,body])=>JSON.stringify(id)+':function(module,exports,require){'+body+'\n}').join(',')}};const cache=Object.create(null);return function require(id){if(!Object.hasOwn(modules,id))throw Error('CF033 unregistered module');if(!Object.hasOwn(cache,id)){const m={exports:{}};cache[id]=m;modules[id](m,m.exports,require);}return cache[id].exports;};})()`;
}
function checkedRecord(cap,record,relative){
 if(!record||record.relative!==relative)throw Error('CF033 exact record');
 const file=path.join(cap.dependency,relative),s=fs.lstatSync(file,{bigint:true}),bytes=fs.readFileSync(file);
 if(fs.realpathSync(file)!==file||!s.isFile()||s.nlink!==1n||![0n,BigInt(process.getuid())].includes(s.uid)||s.mode&0o022n||Number(s.size)!==record.size||crypto.createHash('sha256').update(bytes).digest('hex')!==record.sha256)throw Error('CF033 dependency drift');
 const identity=record.identity?.at(-1);
 for(const [key,field] of [['dev','dev'],['ino','ino'],['mode','mode'],['size','size'],['mtime','mtimeNs'],['ctime','ctimeNs'],['nlink','nlink']])if(identity?.[key]!==String(s[field]))throw Error('CF033 dependency identity drift');
 return bytes.toString();
}
export function chartRegistry(cap){
 if(cap.cf033Chart!==true||cap.reactProduction?.length!==5||cap.chartProduction?.length!==3||cap.chartMetadata?.length!==4)throw Error('CF033 exact capability');
 const registry={};
 for(let i=0;i<5;i++)registry[moduleNames[i]]=checkedRecord(cap,cap.reactProduction[i],reactProductionFiles[i]);
 const pins=['c7f4c7d0c046c5c38923940e43319cc2bcf763a3b27a45e45ac5108a5d57e4e3','5e78de80512a178bc216c1d34383dff1ed7e87a647be4b220c4dd672cf85ca36','9a073bb4a71d6180250b70db22e9120993071cfddd473b1b8d2727182253c79e'];
 for(let i=0;i<3;i++){
  if(cap.chartProduction[i].sha256!==pins[i])throw Error('CF033 code pin');
  registry[moduleNames[i+5]]=checkedRecord(cap,cap.chartProduction[i],chartProductionFiles[i]);
 }
 const metadata=['recharts/package.json','lucide-react/package.json','next/package.json','next/dist/compiled/react-is/package.json'];
 const versions=['3.9.1','1.23.0','16.2.10','19.3.0-canary-3f0b9e61-20260317'];
 const metadataPins=['2a51583aedbb677771dce74309061cfd850cf6a9840132786e13aad5a9e9294b','89b273b576398863371027110beb8ecef8c822dd611c01f34adab5fe503e2e69','57f3d18dd1fbfd586762782d5ab66ba0862380bcdbeec633a5cbe124a1b365ee','043b0164b486c7bb11c2ae4062ea09fe53af170c93e05069f182f34ea15e3244'];
 for(let i=0;i<4;i++)if(cap.chartMetadata[i].sha256!==metadataPins[i]||JSON.parse(checkedRecord(cap,cap.chartMetadata[i],metadata[i])).version!==versions[i])throw Error('CF033 metadata pin');
 for(const [id,file] of Object.entries({Boundary:'src/features/technical/components/technical-boundary-preview.tsx','../lib/strict-boundary-read':'src/features/technical/lib/strict-boundary-read.ts','./boundary-preview':'src/features/technical/lib/boundary-preview.ts','./technical-chart-panel':'src/features/technical/components/technical-chart-panel.tsx','@/features/technical/lib/chart':'src/features/technical/lib/chart.ts','@/shared/lib/format':'src/shared/lib/format.ts'}))registry[id]=ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;
 return registry;
}
export function registryPreflight(registry){
 const require=vm.runInNewContext(moduleProgram(registry),{process:{env:{NODE_ENV:'production'}},console:{log(){},warn(){},error(){}},setTimeout,clearTimeout,performance},{timeout:1000,codeGeneration:{strings:false,wasm:false}});
 const React=require('react'),is=require('react-is'),charts=require('recharts'),icons=require('lucide-react');
 if(React.version!=='19.2.4')throw Error('CF033 React version preflight');
 if(!is.isElement(React.createElement('div'))||!is.isFragment(React.createElement(React.Fragment)))throw Error('CF033 React identity preflight');
 for(const name of ['Area','Bar','BarChart','Brush','CartesianGrid','Cell','ComposedChart','Customized','Line','ReferenceLine','ReferenceArea','ReferenceDot','ResponsiveContainer','Tooltip','XAxis','YAxis'])if(!is.isValidElementType(charts[name]))throw Error('CF033 chart export preflight');
 for(const name of ['useXAxisScale','useYAxisScale'])if(typeof charts[name]!=='function')throw Error('CF033 hook export preflight');
 for(const name of ['MousePointerClick','Info','GitCommitHorizontal','History'])if(!is.isValidElementType(icons[name]))throw Error('CF033 icon export preflight');
 return {element:true,fragment:true,chart:true,icons:true};
}
export function readFixtureBody(req){
 return new Promise((resolve,reject)=>{
  let size=0,done=false;const parts=[];
  const settle=(error,value)=>{if(done)return;done=true;clearTimeout(timer);req.off('data',data);req.off('end',end);req.off('error',errorEvent);if(error)reject(error);else resolve(value);};
  const timer=setTimeout(()=>settle(Object.assign(Error('CF033 body deadline'),{status:422})),5000);
  const data=chunk=>{size+=chunk.length;if(size>1024){settle(Object.assign(Error('CF033 body limit'),{status:422}));req.resume();}else parts.push(chunk);};
  const end=()=>settle(null,Buffer.concat(parts).toString('utf8'));
  const errorEvent=()=>settle(Object.assign(Error('CF033 body unavailable'),{status:422}));
  req.on('data',data);req.on('end',end);req.on('error',errorEvent);
 });
}
function client(packets,nonce){
 // Browser-only closed registry; these calls never resolve filesystem modules.
 // eslint-disable-next-line @typescript-eslint/no-require-imports
 const React=require('react'),root=require('react-dom/client').createRoot(document.getElementById('chart-root'),{onUncaughtError(){fail('RENDER_FAILED');},onRecoverableError(){fail('RENDER_RECOVERY');}}),View=require('Boundary').TechnicalBoundaryPreview;
 let mode='A',actions=0,errors=0,closed=false,interval,deadline;
 const output=document.getElementById('observation'),status=document.getElementById('status');
 function snapshot(){
  const target=document.getElementById('chart-root'),buttons=[...target.querySelectorAll('button')];
  const selected=buttons.find(b=>['3개월','5년'].includes(b.textContent.trim())&&b.classList.contains('bg-white'))?.textContent.trim()??null;
  const geometry=[...target.querySelectorAll('svg.recharts-surface')].map(svg=>{const r=svg.getBoundingClientRect(),s=getComputedStyle(svg);return {width:r.width,height:r.height,display:s.display,visibility:s.visibility,opacity:s.opacity,viewBox:svg.getAttribute('viewBox'),cssWidth:s.width,cssHeight:s.height};});
  const candle=target.querySelector('.recharts-candles rect'),candleGeometry=candle?{x:candle.getAttribute('x'),y:candle.getAttribute('y'),width:candle.getAttribute('width'),height:candle.getAttribute('height'),fill:candle.getAttribute('fill')}:null;
  const data={geometry,candleGeometry,mode,actions,errors,closed,width:innerWidth,height:innerHeight,surfaces:target.querySelectorAll('svg.recharts-surface').length,candles:target.querySelectorAll('.recharts-candles rect').length,icons:target.querySelectorAll('svg.lucide').length,selected,rsi:!!target.querySelector('[class~="h-[92px]"]'),overflow:document.documentElement.scrollWidth>innerWidth+2,activeTag:document.activeElement?.tagName??null};
  output.textContent=JSON.stringify(data).slice(0,16384);
 }
 function stop(){clearInterval(interval);clearTimeout(deadline);for(const b of document.querySelectorAll('#controls button'))b.disabled=true;}
 function fail(code){if(closed)return;closed=true;errors++;status.textContent=code;stop();document.getElementById('cancel').disabled=false;queueMicrotask(()=>root.unmount());snapshot();}
 function render(){const c=packets[mode];root.render(React.createElement(View,{response:c.response,expected:c.expected}));}
 for(const b of document.querySelectorAll('[data-case]'))b.onclick=()=>{if(closed)return;if(++actions>64){fail('ACTION_LIMIT');return;}mode=b.dataset.case;render();};
 document.getElementById('rerender').onclick=()=>{if(closed)return;if(++actions>64){fail('ACTION_LIMIT');return;}render();};
 for(const action of ['complete','cancel'])document.getElementById(action).onclick=async()=>{
  if(closed&&action!=='cancel')return;closed=true;stop();snapshot();
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),5000);
  try{const response=await fetch('/fixture-finish',{method:'POST',headers:{'Content-Type':'application/json','x-fixture-nonce':nonce},body:JSON.stringify({action}),signal:controller.signal});const value=await response.json();if(response.status!==200||value.state!==(action==='complete'?'completed':'cancelled'))throw Error('ACK');status.textContent='lifecycle '+value.state+' · UI evidence separate';}
  catch{status.textContent='TERMINAL_ACK_UNCONFIRMED';}finally{clearTimeout(timer);root.unmount();snapshot();}
 };
 addEventListener('error',e=>{e.preventDefault();fail('CLIENT_ERROR');});addEventListener('unhandledrejection',e=>{e.preventDefault();fail('CLIENT_REJECTION');});addEventListener('pagehide',stop);
 interval=setInterval(snapshot,250);deadline=setTimeout(()=>fail('FIXTURE_EXPIRED'),590000);render();snapshot();
}
const css=`*{box-sizing:border-box}body{margin:0;padding:16px;background:#f1f5f9;color:#334155;font:14px system-ui,sans-serif}main{max-width:1120px;margin:auto;min-width:0}button{cursor:pointer;padding:8px 12px;border:1px solid #cbd5e1;border-radius:8px;background:white;color:#334155}button:focus-visible{outline:3px solid #6366f1;outline-offset:2px}button:disabled{opacity:.5}#controls{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}#observation{display:block;white-space:pre-wrap;overflow-wrap:anywhere;font:12px monospace;padding:8px;background:white}section{min-width:0}[class~="flex"]{display:flex}[class~="flex-wrap"]{flex-wrap:wrap}[class~="items-center"]{align-items:center}[class~="justify-between"]{justify-content:space-between}[class~="gap-2"]{gap:8px}[class~="gap-3"]{gap:12px}[class~="p-6"]{padding:20px}[class~="mt-4"]{margin-top:16px}[class~="bg-white"]{background:white}[class~="bg-indigo-50"]{background:#eef2ff}[class~="rounded-2xl"]{border-radius:16px}[class~="h-[288px]"]{height:288px}[class~="h-[92px]"]{height:92px}[class~="h-[80px]"]{height:80px}.space-y-4>*+*{margin-top:16px}h1,h2{font-size:18px}ul{padding-left:20px}@media(max-width:440px){body{padding:8px}[class~="p-6"]{padding:12px}button{padding:8px} }`;
async function bounded(job,ms){let timer;try{return await Promise.race([job,new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('CF033 settlement deadline')),ms);})]);}finally{clearTimeout(timer);}}
async function main(){
 const cap=JSON.parse(fs.readFileSync(process.env.ST001_SAFE_CAP,'utf8'));
 if(cap.cf033Chart!==true||cap.workload!=='unit'||cap.ports.length!==2||cap.lifetime>600||cap.root!==process.cwd())throw Error('CF033 browser capability');
 const registry=chartRegistry(cap);console.log('CF033_REGISTRY '+JSON.stringify(registryPreflight(registry)));
 const packets=fixtureCases(JSON.parse(fs.readFileSync('tests/fixtures/cf031-technical-boundary-read.json','utf8')));
 const bundle='const require='+moduleProgram(registry)+';('+client.toString()+')('+JSON.stringify(packets)+','+JSON.stringify(cap.nonce)+');';
 const origin='http://127.0.0.1:'+cap.ports[0],proof={nonce:cap.nonce,pid:process.pid,cwd:process.cwd(),port:cap.ports[0]};
 const counts=Object.fromEntries(['sessionGET','preparePOST','prepareGET','prepareDELETE','confirmPOST','outcomeGET','model','provider'].map(k=>[k,0]));
 let requests=0,ackResponse,expiry,resolveStopped,closeTask,settlementBefore=Infinity;
 const stopped=new Promise(resolve=>{resolveStopped=resolve;}),pending=new Set();
 const server=http.createServer(async(req,res)=>{
  res.setHeader('Cache-Control','no-store');res.setHeader('Content-Security-Policy',`default-src 'none'; script-src 'nonce-${cap.nonce}'; style-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'`);
  const reply=(status,body,type='application/json')=>{res.writeHead(status,{'Content-Type':type,'Connection':'close'});res.end(body);};
  try{
   if(++requests>128){reply(429,'{}');if(terminal.open())void terminal.finish('failed').catch(()=>resolveStopped());return;}
   if(!terminal.open()){reply(409,'{}');return;}
   if(req.headers.host!=='127.0.0.1:'+proof.port){reply(421,'{}');return;}
   const route=fixtureTarget(req.url);if(route.status!==200){reply(route.status,'{}');return;}
   if(route.kind==='finish'){
    if(req.method!=='POST'||req.headers.origin!==origin||req.headers['x-fixture-nonce']!==cap.nonce||req.headers['content-type']!=='application/json'){reply(403,'{}');return;}
    const action=terminalAction(await readFixtureBody(req));if(!terminal.open()){reply(409,'{}');return;}
    ackResponse=res;try{await terminal.finish(action);}catch(error){resolveStopped();throw error;}return;
   }
   if(req.method!=='GET'){reply(405,'{}');return;}
   const done=new Promise(resolve=>{res.once('finish',resolve);res.once('close',resolve);});pending.add(done);void done.finally(()=>pending.delete(done));
   if(route.kind==='bundle')reply(200,bundle,'application/javascript');
   else if(route.kind==='css')reply(200,css,'text/css');
   else reply(200,`<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CF033 actual Technical chart fixture</title><link rel="stylesheet" href="/fixture.css"></head><body><main><h1>CF033 실제 합성 차트 · 실제 provider/저장 없음</h1><p id="status">active · lifecycle and UI evidence separate</p><div id="controls">${[['A','정상 A'],['B','새 binding B'],['empty','전부 빈 자료'],['missing','전부 미제공'],['error','typed 오류'],['invalid','잘못된 packet']].map(([key,label])=>'<button data-case="'+key+'">'+label+'</button>').join('')}<button id="rerender">같은 binding rerender</button><button id="complete">fixture 완료</button><button id="cancel">fixture 취소</button></div><output id="observation"></output><div id="chart-root"></div></main><script nonce="${cap.nonce}" src="/bundle.js"></script></body></html>`,'text/html');
  }catch(error){if(!res.headersSent)reply(error.status??422,'{}');else res.end();}
 });
 server.headersTimeout=5000;server.requestTimeout=5000;server.keepAliveTimeout=1000;
 const close=()=>{closeTask??=new Promise(resolve=>{let timer;const done=()=>{clearTimeout(timer);resolve();};server.close(done);server.closeIdleConnections();timer=setTimeout(()=>{server.closeAllConnections();done();},Math.max(1,Math.min(4000,settlementBefore-Date.now()-10)));timer.unref();});return closeTask;};
 const terminal=createFixtureTerminal({stopWork(){clearTimeout(expiry);settlementBefore=Date.now()+5000;},async drain(){await bounded(Promise.all([...pending]),Math.max(1,settlementBefore-Date.now()));},async writeReceipt({action,state}){
  const receipt={schema:'cf025.terminal.v1',...proof,action,state,counts,browser:browserNotExecuted()};fs.writeFileSync('cf025-terminal.json',JSON.stringify(receipt),{mode:0o600,flag:'wx'});return receipt;
 },async ack(receipt){if(ackResponse)await bounded(new Promise(resolve=>{ackResponse.writeHead(200,{'Content-Type':'application/json'});ackResponse.end(JSON.stringify({state:receipt.state}),()=>resolve());}),Math.max(1,settlementBefore-Date.now()));},close,settled(){resolveStopped();}});
 try{
  await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(proof.port,'127.0.0.1',resolve);});
  fs.writeFileSync('cf019-ready.json',JSON.stringify(proof),{mode:0o600,flag:'wx'});
  expiry=setTimeout(()=>{if(terminal.open())void terminal.finish('timed_out').catch(()=>resolveStopped());},590000);
  const stop=()=>{if(terminal.open())void terminal.finish('cancel').catch(()=>resolveStopped());};process.once('SIGTERM',stop);process.once('SIGINT',stop);
  await stopped;process.exitCode=['completed','cancelled'].includes(terminal.phase)?0:1;
 }finally{clearTimeout(expiry);if(fs.existsSync('cf019-ready.json'))fs.unlinkSync('cf019-ready.json');await close();}
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href)await main().catch(()=>{console.error('CF033_FIXTURE_FAILED');process.exitCode=1;});
