import "server-only";
import { sessionBackendUrl } from './session-backend';
import { flowDemoEnabled } from './flow-demo-config';
import { randomUUID } from 'node:crypto';

const demoPath='/api/flow/synthetic-demo/runs';
export function demoProxyError(code:string,status:number) {
  return Response.json({request_id:randomUUID(),data:null,error:{code,message:'합성 데모 요청을 처리할 수 없습니다.'}},
    {status,headers:{'Cache-Control':'private, no-store',Vary:'Cookie, Origin'}});
}


export async function sessionProxy(request: Request, path: string, query = '') {
  const demo=path===demoPath || path.startsWith(demoPath+'/');
  if(demo && !flowDemoEnabled())return demoProxyError('FEATURE_UNAVAILABLE',403);
  const base = sessionBackendUrl();
  const headers = new Headers({'Cache-Control': 'private, no-store', Vary: 'Cookie, Origin'});
  if (!base && demo)return demoProxyError('SERVICE_UNAVAILABLE',503);
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
      if(demo)return demoProxyError('AUTH_REQUEST_INVALID',403);
      return Response.json({detail:{code:'AUTH_REQUEST_INVALID',message:'잘못된 인증 요청입니다.'}},{status:403,headers});
    }
  }
  let body: ArrayBuffer | undefined;
  if(demo) {
    const detail=/^\/api\/flow\/synthetic-demo\/runs\/[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$/.test(path);
    if(query || new URL(request.url).search || !(request.method==='POST' && path===demoPath || request.method==='GET' && detail))return demoProxyError('INPUT_INVALID',422);
    if(request.method==='POST') {
      const content=request.headers.get('content-type') ?? '';
      const length=request.headers.get('content-length');
      if(!/^application\/json(?:\s*;\s*charset\s*=\s*(?:utf-8|"utf-8"))?\s*$/i.test(content) ||
        ![null,'identity'].includes(request.headers.get('content-encoding')?.toLowerCase() ?? null) ||
        length!==null && (!/^\d+$/.test(length) || Number(length)>4096))return demoProxyError('INPUT_INVALID',422);
      const reader=request.body?.getReader();const chunks:Uint8Array[]=[];let size=0;
      try {
        if(!reader)return demoProxyError('INPUT_INVALID',422);
        while(true){const chunk=await reader.read();if(chunk.done)break;size+=chunk.value.byteLength;if(size>4096){await reader.cancel();return demoProxyError('INPUT_INVALID',422);}chunks.push(chunk.value);}
        const bytes=new Uint8Array(size);let offset=0;for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.byteLength;}body=bytes.buffer;
      }catch{return demoProxyError('INPUT_INVALID',422);}finally{reader?.releaseLock();}
    }
  }
  const forwarded = new Headers({Accept:'application/json'});
  // No caller-supplied owner/user/service headers; Backend verifies cookie + Origin + CSRF.
  for (const name of ['cookie','origin','x-csrf-token']) {
    const value = request.headers.get(name);
    if (value) forwarded.set(name,value);
  }
  if(body!==undefined)forwarded.set('content-type',request.headers.get('content-type') ?? 'application/json');
  try {
    const upstream = await fetch(base + path + query, {method:request.method,headers:forwarded,...(body===undefined?{}:{body}),cache:'no-store',redirect:'manual'});
    for (const cookie of upstream.headers.getSetCookie()) headers.append('Set-Cookie',cookie);
    for (const key of ['content-type','location']) {
      const value=upstream.headers.get(key);
      if (value) headers.set(key,value);
    }
    return new Response(upstream.status===204 ? null : upstream.body,{status:upstream.status,headers});
  } catch {
    if(demo)return demoProxyError('SERVICE_UNAVAILABLE',503);
    return Response.json({detail:{code:'SERVICE_UNAVAILABLE',message:'요청을 처리할 수 없습니다.'}},{status:503,headers});
  }
}
