import { fundamentalAnalysisEnabled } from './fundamental-analysis-config';
import "server-only";
import { sessionBackendUrl } from './session-backend';
import { flowDemoEnabled } from './flow-demo-config';
import { flowAnalysisEnabled } from './flow-analysis-config';
import { randomUUID } from 'node:crypto';

const demoPath='/api/flow/synthetic-demo/runs';
const analysisPath='/api/flow/analyses';
export function demoProxyError(code:string,status:number) {
  return Response.json({request_id:randomUUID(),data:null,error:{code,message:'합성 데모 요청을 처리할 수 없습니다.'}},
    {status,headers:{'Cache-Control':'private, no-store',Vary:'Cookie, Origin'}});
}


export function analysisProxyError(code:string,status:number){
  return Response.json({request_id:randomUUID(),data:null,error:{code,message:'분석 요청을 처리할 수 없습니다.'}},
    {status,headers:{'Cache-Control':'private, no-store',Vary:'Cookie, Origin'}});
}

export function coreProxyError(code:string,status:number){
 return Response.json({schema_version:'supervisor.core.v1',request_id:randomUUID(),trace_id:randomUUID(),data:null,error:{code,message:'Supervisor request unavailable'}},{status,headers:{'Cache-Control':'private, no-store',Vary:'Cookie, Origin'}});
}

async function boundedRead(reader:ReadableStreamDefaultReader<Uint8Array>,signal:AbortSignal|undefined){
  if(!signal)return reader.read();
  if(signal.aborted){void reader.cancel().catch(()=>{});throw Error('Analysis deadline exceeded');}
  return new Promise<ReadableStreamReadResult<Uint8Array>>((resolve,reject)=>{
    const aborted=()=>{void reader.cancel().catch(()=>{});reject(Error('Analysis deadline exceeded'));};
    signal.addEventListener('abort',aborted,{once:true});
    reader.read().then(resolve,reject).finally(()=>signal.removeEventListener('abort',aborted));
  });
}

export async function sessionProxy(request: Request, path: string, query = '') {
  const core=path.startsWith('/api/supervisor/core');
  const planning=path==='/api/flow/plans'||path.startsWith('/api/flow/plans/');
  const demo=path===demoPath || path.startsWith(demoPath+'/');
  const fundamental=path==='/api/fundamental/analyses'||path.startsWith('/api/fundamental/analyses/')||path==='/api/fundamental/reports'||path.startsWith('/api/fundamental/reports/');
  const fundamentalReports=fundamental&&path.startsWith('/api/fundamental/reports');
  const currentAnalysisPath=fundamental?'/api/fundamental/analyses':analysisPath;
  const analysis=core || planning || fundamental || path===analysisPath || path.startsWith(analysisPath+'/');
  const guarded=demo||analysis;
  const reject=core?coreProxyError:analysis?analysisProxyError:demoProxyError;
  if(analysis&&!(fundamental?fundamentalAnalysisEnabled():flowAnalysisEnabled()))return reject('FEATURE_UNAVAILABLE',403);
  const analysisSignal=analysis?AbortSignal.timeout(core?(path==='/api/supervisor/core/requests'&&request.method==='POST'?145000:16000):planning?12000:fundamental?70000:130000):undefined;
  if(demo && !flowDemoEnabled())return demoProxyError('FEATURE_UNAVAILABLE',403);
  const base = sessionBackendUrl();
  const headers = new Headers({'Cache-Control': 'private, no-store', Vary: 'Cookie, Origin'});
  if (!base && guarded)return reject('SERVICE_UNAVAILABLE',503);
  if (!base) return Response.json({detail:{code:'AUTH_UNCONFIGURED',message:'로그인 설정이 필요합니다.'}}, {status:503,headers});
  // Canonical local deployment only. Synthetic test origins/ephemeral backends
  // and explicitly configured HTTPS deployments retain their own server config.
  if (base === 'http://localhost:8200') {
    const url = new URL(request.url);
    const host = request.headers.get('host');
    const forwardedHost = request.headers.get('x-forwarded-host');
    const origin = request.headers.get('origin');
    if (url.origin !== 'http://localhost:3200' || host !== 'localhost:3200' ||
        forwardedHost !== null && forwardedHost !== 'localhost:3200' ||
        origin !== null && origin !== 'http://localhost:3200') {
      if(guarded)return reject('AUTH_REQUEST_INVALID',403);
      return Response.json({detail:{code:'AUTH_REQUEST_INVALID',message:'잘못된 인증 요청입니다.'}},{status:403,headers});
    }
  }
  let body: ArrayBuffer | undefined;
  if(guarded) {
    const idPattern='[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}';
    const root=core?(path.startsWith('/api/supervisor/core/requests')?'/api/supervisor/core/requests':'/api/supervisor/core/prepare'):planning?'/api/flow/plans':fundamentalReports?'/api/fundamental/reports':analysis?currentAnalysisPath:demoPath;
    const detail=new RegExp('^'+root+'/'+idPattern+'$').test(path);
    if(fundamentalReports){
      const params=new URLSearchParams(query.startsWith('?')?query.slice(1):query);
      if(!(request.method==='GET'&&(path===root||detail)||request.method==='DELETE'&&detail))return reject('INPUT_INVALID',422);
      if(detail&&(query||new URL(request.url).search))return reject('INPUT_INVALID',422);
      if([...params.keys()].some(k=>!['stock_code','limit','offset'].includes(k)||params.getAll(k).length!==1))return reject('INPUT_INVALID',422);
      for(const [key,value] of params){if(!/^[0-9]+$/.test(value)||key==='stock_code'&&!/^[0-9]{6}$/.test(value)||key==='limit'&&(!Number.isSafeInteger(Number(value))||Number(value)<1||Number(value)>100)||key==='offset'&&!Number.isSafeInteger(Number(value)))return reject('INPUT_INVALID',422);}
    }else if(query || new URL(request.url).search || !(request.method==='POST' && path===root || !planning && request.method==='GET' && detail))return reject('INPUT_INVALID',422);
    if(request.method==='POST') {
      const content=request.headers.get('content-type') ?? '';
      const length=request.headers.get('content-length');
      if(!/^application\/json(?:\s*;\s*charset\s*=\s*(?:utf-8|"utf-8"))?\s*$/i.test(content) ||
        ![null,'identity'].includes(request.headers.get('content-encoding')?.toLowerCase() ?? null) ||
        length!==null && (!/^\d+$/.test(length) || Number(length)>(core?16384:4096)))return reject('INPUT_INVALID',422);
      const reader=request.body?.getReader();const chunks:Uint8Array[]=[];let size=0;
      try {
        if(!reader)return reject('INPUT_INVALID',422);
        while(true){const chunk=await boundedRead(reader,analysisSignal);if(chunk.done)break;size+=chunk.value.byteLength;if(size>(core?16384:4096)){await reader.cancel();return reject('INPUT_INVALID',422);}chunks.push(chunk.value);}
        const bytes=new Uint8Array(size);let offset=0;for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.byteLength;}body=bytes.buffer;
      }catch{return reject((core||planning)&&analysisSignal?.aborted?'DEADLINE_EXCEEDED':'INPUT_INVALID',(core||planning)&&analysisSignal?.aborted?504:422);}finally{try{reader?.releaseLock();}catch{ /* cancelled read */ }}
    }
  }
  const forwarded = new Headers({Accept:'application/json',...((core||planning)?{'Accept-Encoding':'identity'}:{})});
  // No caller-supplied owner/user/service headers; Backend verifies cookie + Origin + CSRF.
  for (const name of ['cookie','origin','x-csrf-token']) {
    const value = request.headers.get(name);
    if (value) forwarded.set(name,value);
  }
  if(body!==undefined)forwarded.set('content-type',request.headers.get('content-type') ?? 'application/json');
  try {
    const upstream = await fetch(base + path + query, {method:request.method,headers:forwarded,...(body===undefined?{}:{body}),cache:'no-store',redirect:'manual',...(analysis?{signal:analysisSignal}:{})});
    if((core||planning)&&(upstream.status>=300&&upstream.status<400||![null,'identity'].includes(upstream.headers.get('content-encoding')?.toLowerCase()??null))){await upstream.body?.cancel();return reject('SERVICE_UNAVAILABLE',503);}
    for (const cookie of upstream.headers.getSetCookie()) headers.append('Set-Cookie',cookie);
    for (const key of ['content-type','location']) {
      const value=upstream.headers.get(key);
      if (value) headers.set(key,value);
    }
    if(analysis){
      const reader=upstream.body?.getReader();const chunks:Uint8Array[]=[];let size=0;
      try{if(reader)while(true){const next=await boundedRead(reader,analysisSignal);if(next.done)break;size+=next.value.byteLength;if(size>(core?65536:planning?16384:fundamentalReports?2097152:32768)){await reader.cancel();return reject('RESULT_CONTRACT_INVALID',502);}chunks.push(next.value);}}
      finally{try{reader?.releaseLock();}catch{ /* cancelled read */ }}
      const bytes=new Uint8Array(size);let offset=0;for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.byteLength;}
      return new Response(upstream.status===204?null:bytes,{status:upstream.status,headers});
    }
    return new Response(upstream.status===204 ? null : upstream.body,{status:upstream.status,headers});
  } catch {
    if(guarded)return reject((core||planning)&&analysisSignal?.aborted?'DEADLINE_EXCEEDED':'SERVICE_UNAVAILABLE',(core||planning)&&analysisSignal?.aborted?504:503);
    return Response.json({detail:{code:'SERVICE_UNAVAILABLE',message:'요청을 처리할 수 없습니다.'}},{status:503,headers});
  }
}
