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

const moduleNames=['react','react/jsx-runtime','react-dom','react-dom/client','scheduler','recharts','lucide-react','react-is','Boundary','../lib/strict-boundary-read','./boundary-preview','./technical-chart-panel','@/features/technical/lib/chart','@/shared/lib/format','Owned','./technical-boundary-preview','../lib/owned-report-read','@/features/flow/lib/analysis-request','./strict-boundary-read'];
export function fixtureTarget(target){
 if(typeof target==='string'){const owned=ownedFixtureTarget(target);if(owned)return owned;}
 if(typeof target!=='string'||target.length>2048||!target.startsWith('/')||target.startsWith('//')||/[?%#\\\x00-\x20\x7f]/.test(target)||target.split('/').some(p=>p==='.'||p==='..'))return {status:422,kind:'invalid'};
 const routes={'/technical-preview':'html','/bundle.js':'bundle','/fixture.css':'css','/fixture-finish':'finish'};
 return Object.hasOwn(routes,target)?{status:200,kind:routes[target]}:{status:404,kind:'missing'};
}

const ownedUuid='[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}';
export function ownedFixtureTarget(target){
 if(typeof target!=='string'||target.length>512||!target.startsWith('/')||target.startsWith('//')||/[#\\\x00-\x20\x7f]/.test(target))return null;
 const [pathname,...queries]=target.split('?');if(queries.length>1)return {status:422,kind:'invalid'};
 const list=pathname==='/reports/technical'||pathname==='/api/private/technical/owned-reports';
 const detail=new RegExp('^(?:/reports/technical|/api/private/technical/owned-reports)/'+ownedUuid+'$').test(pathname);
 if(!list&&!detail){if(pathname==='/api/auth/session'&&queries.length===0)return {status:200,kind:'session'};if(pathname==='/fixture-owned-mode'&&queries.length===0)return {status:200,kind:'owned-mode'};return null;}
 if(detail&&queries.length)return {status:422,kind:'invalid'};
 const query=new URLSearchParams(queries[0]??''),values=Object.fromEntries(query);
 if([...query].length!==Object.keys(values).length||Object.keys(values).some(k=>!['stock_code','limit','offset'].includes(k))||values.stock_code!==undefined&&!/^[0-9]{6}$/.test(values.stock_code)||['limit','offset'].some(k=>values[k]!==undefined&&!/^[0-9]{1,5}$/.test(values[k]))||Number(values.limit??10)<1||Number(values.limit??10)>20||Number(values.offset??0)>10000)return {status:422,kind:'invalid'};
 return {status:200,kind:pathname.startsWith('/api/')?(list?'owned-list':'owned-detail'):'owned-html',reportId:detail?pathname.split('/').at(-1):null,query:values};
}
export function ownedMode(value){
 let packet;try{packet=JSON.parse(value);}catch{throw Error('CF036 mode invalid');}
 if(!packet||Object.keys(packet).length!==1||!['normal','empty','missing','unavailable','long-error','unauthorized','owner-change','slow'].includes(packet.mode))throw Error('CF036 mode invalid');return packet.mode;
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
 for(const [id,file] of Object.entries({Boundary:'src/features/technical/components/technical-boundary-preview.tsx','../lib/strict-boundary-read':'src/features/technical/lib/strict-boundary-read.ts','./boundary-preview':'src/features/technical/lib/boundary-preview.ts','./technical-chart-panel':'src/features/technical/components/technical-chart-panel.tsx','@/features/technical/lib/chart':'src/features/technical/lib/chart.ts','@/shared/lib/format':'src/shared/lib/format.ts',Owned:'src/features/technical/components/owned-report-view.tsx','./technical-boundary-preview':'src/features/technical/components/technical-boundary-preview.tsx','../lib/owned-report-read':'src/features/technical/lib/owned-report-read.ts','./strict-boundary-read':'src/features/technical/lib/strict-boundary-read.ts','@/features/flow/lib/analysis-request':'src/features/flow/lib/analysis-request.ts'}))registry[id]=ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;
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
function ownedClient(nonce){
 // eslint-disable-next-line @typescript-eslint/no-require-imports
 const React=require('react'),root=require('react-dom/client').createRoot(document.getElementById('chart-root')),View=require('Owned').OwnedReportView;
 const output=document.getElementById('observation'),status=document.getElementById('status');let closed=false,interval,deadline;
 const id=()=>location.pathname==='/reports/technical'?null:location.pathname.split('/').at(-1);
 function render(){root.render(React.createElement(View,{reportId:id()}));}
 function snapshot(){const target=document.getElementById('chart-root');output.textContent=JSON.stringify({path:location.pathname,width:innerWidth,height:innerHeight,overflow:document.documentElement.scrollWidth>innerWidth+2,busy:target.querySelector('[aria-busy]')?.getAttribute('aria-busy')??null,alerts:[...target.querySelectorAll('[role=alert]')].map(n=>n.textContent),status:[...target.querySelectorAll('[role=status]')].map(n=>n.textContent),links:[...target.querySelectorAll('a')].map(n=>n.getAttribute('href')),surfaces:target.querySelectorAll('svg.recharts-surface').length,candles:target.querySelectorAll('.recharts-candles rect').length,activeTag:document.activeElement?.tagName??null}).slice(0,16384);}
 function stop(){clearInterval(interval);clearTimeout(deadline);}
 for(const b of document.querySelectorAll('[data-owned-mode]'))b.onclick=async()=>{try{const response=await fetch('/fixture-owned-mode',{method:'POST',headers:{'content-type':'application/json','x-fixture-nonce':nonce},body:JSON.stringify({mode:b.dataset.ownedMode})});if(response.status!==200)throw Error('mode');status.textContent='synthetic GET mode '+b.dataset.ownedMode+' · use explicit retry';}catch{status.textContent='MODE_UNAVAILABLE';}};
 document.getElementById('replace-report').onclick=()=>{const next=id()==='00000000-0000-4000-8000-000000000006'?'00000000-0000-4000-8000-000000000016':'00000000-0000-4000-8000-000000000006';history.pushState(null,'','/reports/technical/'+next);dispatchEvent(new PopStateEvent('popstate'));render();};
 for(const action of ['complete','cancel'])document.getElementById(action).onclick=async()=>{if(closed)return;closed=true;stop();snapshot();const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),5000);try{const response=await fetch('/fixture-finish',{method:'POST',headers:{'Content-Type':'application/json','x-fixture-nonce':nonce},body:JSON.stringify({action}),signal:controller.signal});const result=await response.json();if(response.status!==200||result.state!==(action==='complete'?'completed':'cancelled'))throw Error('ACK');status.textContent='lifecycle '+result.state+' · UI evidence separate';}catch{status.textContent='TERMINAL_ACK_UNCONFIRMED';}finally{clearTimeout(timer);root.unmount();snapshot();}};
 addEventListener('error',()=>{status.textContent='OWNED_CLIENT_ERROR';});addEventListener('unhandledrejection',()=>{status.textContent='OWNED_CLIENT_REJECTION';});addEventListener('pagehide',stop);interval=setInterval(snapshot,250);deadline=setTimeout(()=>{stop();root.unmount();status.textContent='FIXTURE_EXPIRED';},590000);render();snapshot();
}
const css=`*{box-sizing:border-box}body{margin:0;padding:16px;background:#f1f5f9;color:#334155;font:14px system-ui,sans-serif}main{max-width:1120px;margin:auto;min-width:0}button{cursor:pointer;padding:8px 12px;border:1px solid #cbd5e1;border-radius:8px;background:white;color:#334155}button:focus-visible{outline:3px solid #6366f1;outline-offset:2px}button:disabled{opacity:.5}#controls{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}#observation{display:block;white-space:pre-wrap;overflow-wrap:anywhere;font:12px monospace;padding:8px;background:white}section{min-width:0}[class~="flex"]{display:flex}[class~="flex-wrap"]{flex-wrap:wrap}[class~="items-center"]{align-items:center}[class~="justify-between"]{justify-content:space-between}[class~="gap-2"]{gap:8px}[class~="gap-3"]{gap:12px}[class~="p-6"]{padding:20px}[class~="mt-4"]{margin-top:16px}[class~="bg-white"]{background:white}[class~="bg-indigo-50"]{background:#eef2ff}[class~="rounded-2xl"]{border-radius:16px}[class~="h-[288px]"]{height:288px}[class~="h-[92px]"]{height:92px}[class~="h-[80px]"]{height:80px}.space-y-4>*+*{margin-top:16px}h1,h2{font-size:18px}ul{padding-left:20px}@media(max-width:440px){body{padding:8px}[class~="p-6"]{padding:12px}button{padding:8px} }`;
async function bounded(job,ms){let timer;try{return await Promise.race([job,new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('CF033 settlement deadline')),ms);})]);}finally{clearTimeout(timer);}}
async function main(){
 const cap=JSON.parse(fs.readFileSync(process.env.ST001_SAFE_CAP,'utf8'));
 if(cap.cf033Chart!==true||cap.workload!=='unit'||cap.ports.length!==2||cap.lifetime>600||cap.root!==process.cwd())throw Error('CF033 browser capability');
 const registry=chartRegistry(cap);console.log('CF033_REGISTRY '+JSON.stringify(registryPreflight(registry)));
 const packets=fixtureCases(JSON.parse(fs.readFileSync('tests/fixtures/cf031-technical-boundary-read.json','utf8'))),ownedPackets=JSON.parse(fs.readFileSync('tests/fixtures/cf036-technical-owned-read.json','utf8'));
 const bundle='const require='+moduleProgram(registry)+';if(location.pathname.startsWith(\'/reports/technical\')){('+ownedClient.toString()+')('+JSON.stringify(cap.nonce)+');}else{('+client.toString()+')('+JSON.stringify(packets)+','+JSON.stringify(cap.nonce)+');}';
 const origin='http://127.0.0.1:'+cap.ports[0],proof={nonce:cap.nonce,pid:process.pid,cwd:process.cwd(),port:cap.ports[0]};
 const counts=Object.fromEntries(['sessionGET','preparePOST','prepareGET','prepareDELETE','confirmPOST','outcomeGET','model','provider'].map(k=>[k,0]));
 let ownedModeName='normal',ownedSessionReads=0;const ownedCounts={listGET:0,detailGET:0,modePOST:0};
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
   if(route.kind==='owned-mode'){
    if(req.method!=='POST'||req.headers.origin!==origin||req.headers['x-fixture-nonce']!==cap.nonce||req.headers['content-type']!=='application/json'){reply(403,'{}');return;}
    ownedModeName=ownedMode(await readFixtureBody(req));ownedSessionReads=0;ownedCounts.modePOST++;reply(200,JSON.stringify({mode:ownedModeName}));return;
   }
   if(req.method!=='GET'){reply(405,'{}');return;}
   const done=new Promise(resolve=>{res.once('finish',resolve);res.once('close',resolve);});pending.add(done);void done.finally(()=>pending.delete(done));
   if(['session','owned-list','owned-detail'].includes(route.kind)){
    if(route.kind==='session'){
     counts.sessionGET++;ownedSessionReads++;
     if(ownedModeName==='unauthorized'){reply(401,'{}');return;}
     reply(200,JSON.stringify({user_id:ownedModeName==='owner-change'&&ownedSessionReads%2===0?'40000000-0000-4000-8000-000000000002':'40000000-0000-4000-8000-000000000001',csrf_token:'synthetic-owned-session'}));return;
    }
    ownedCounts[route.kind==='owned-list'?'listGET':'detailGET']++;
    const mode=ownedModeName;
    if(mode==='slow')await new Promise(resolve=>{const timer=setTimeout(resolve,1200);res.once('close',()=>{clearTimeout(timer);resolve();});});
    if(res.destroyed)return;
    const packet=structuredClone(mode==='empty'?ownedPackets.empty:route.kind==='owned-list'?ownedPackets.list:route.reportId===ownedPackets.detail.data.report_id?ownedPackets.detail:route.reportId===ownedPackets.second_detail.data.report_id?ownedPackets.second_detail:ownedPackets.error);
    let code=packet.data===null?404:200;
    if(['missing','unavailable','long-error'].includes(mode)){packet.data=null;code=mode==='missing'?404:503;packet.error={code:mode==='missing'?'RESOURCE_NOT_FOUND':'SERVICE_UNAVAILABLE',message:mode==='long-error'?'synthetic-private-long-message-'.repeat(200):'Technical result unavailable'};}
    if(route.kind==='owned-list'&&packet.data){const limit=Number(route.query.limit??10),offset=Number(route.query.offset??0);packet.data.items=packet.data.items.filter(item=>!route.query.stock_code||item.stock.stock_code===route.query.stock_code);const selected=packet.data.items.slice(offset,offset+limit);Object.assign(packet.data,{items:selected,limit,offset,has_more:packet.data.items.length>offset+limit});}
    reply(code,JSON.stringify(packet));return;
   }
   if(route.kind==='owned-html'){reply(200,`<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CF036 actual owned-read fixture</title><link rel="stylesheet" href="/fixture.css"></head><body><main><h1>CF036 본인 저장 차트 · 합성 session/GET</h1><p id="status">active · actual React with synthetic HTTP</p><div id="controls"><a href="/reports/technical">저장 차트 목록</a><a href="/technical-preview">기존 차트 fixture</a>${['normal','empty','missing','unavailable','long-error','unauthorized','owner-change','slow'].map(mode=>'<button data-owned-mode="'+mode+'">'+mode+'</button>').join('')}<button id="replace-report">다른 report 선택</button><button id="complete">fixture 완료</button><button id="cancel">fixture 취소</button></div><output id="observation"></output><div id="chart-root"></div></main><script nonce="${cap.nonce}" src="/bundle.js"></script></body></html>`,'text/html');return;}
   if(route.kind==='bundle')reply(200,bundle,'application/javascript');
   else if(route.kind==='css')reply(200,css,'text/css');
   else reply(200,`<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CF033 actual Technical chart fixture</title><link rel="stylesheet" href="/fixture.css"></head><body><main><h1>CF033 실제 합성 차트 · 실제 provider/저장 없음</h1><p id="status">active · lifecycle and UI evidence separate</p><div id="controls">${[['A','정상 A'],['B','새 binding B'],['empty','전부 빈 자료'],['missing','전부 미제공'],['error','typed 오류'],['invalid','잘못된 packet']].map(([key,label])=>'<button data-case="'+key+'">'+label+'</button>').join('')}<button id="rerender">같은 binding rerender</button><button id="complete">fixture 완료</button><button id="cancel">fixture 취소</button></div><output id="observation"></output><div id="chart-root"></div></main><script nonce="${cap.nonce}" src="/bundle.js"></script></body></html>`,'text/html');
  }catch(error){if(!res.headersSent)reply(error.status??422,'{}');else res.end();}
 });
 server.headersTimeout=5000;server.requestTimeout=5000;server.keepAliveTimeout=1000;
 const close=()=>{closeTask??=new Promise(resolve=>{let timer;const done=()=>{clearTimeout(timer);resolve();};server.close(done);server.closeIdleConnections();timer=setTimeout(()=>{server.closeAllConnections();done();},Math.max(1,Math.min(4000,settlementBefore-Date.now()-10)));timer.unref();});return closeTask;};
 const terminal=createFixtureTerminal({stopWork(){clearTimeout(expiry);settlementBefore=Date.now()+5000;},async drain(){await bounded(Promise.all([...pending]),Math.max(1,settlementBefore-Date.now()));},async writeReceipt({action,state}){
  const ownedRecord={schema:'cf036.browser-counts.v1',...proof,counts:ownedCounts,mode:ownedModeName};fs.writeFileSync('cf036-owned-counts.json',JSON.stringify(ownedRecord),{mode:0o600,flag:'wx'});console.log('CF036_OWNED_COUNTS '+JSON.stringify(ownedRecord));
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
