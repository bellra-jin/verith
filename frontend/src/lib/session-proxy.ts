import "server-only";
import { sessionBackendUrl } from './session-backend';

export async function sessionProxy(request: Request, path: string, query = '') {
  const base = sessionBackendUrl();
  const headers = new Headers({'Cache-Control': 'private, no-store', Vary: 'Cookie, Origin'});
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
      return Response.json({detail:{code:'AUTH_REQUEST_INVALID',message:'잘못된 인증 요청입니다.'}},{status:403,headers});
    }
  }
  const forwarded = new Headers({Accept:'application/json'});
  // No caller-supplied owner/user/service headers; Backend verifies cookie + Origin + CSRF.
  for (const name of ['cookie','origin','x-csrf-token']) {
    const value = request.headers.get(name);
    if (value) forwarded.set(name,value);
  }
  try {
    const upstream = await fetch(base + path + query, {method:request.method,headers:forwarded,cache:'no-store',redirect:'manual'});
    for (const cookie of upstream.headers.getSetCookie()) headers.append('Set-Cookie',cookie);
    for (const key of ['content-type','location']) {
      const value=upstream.headers.get(key);
      if (value) headers.set(key,value);
    }
    return new Response(upstream.status===204 ? null : upstream.body,{status:upstream.status,headers});
  } catch {
    return Response.json({detail:{code:'SERVICE_UNAVAILABLE',message:'요청을 처리할 수 없습니다.'}},{status:503,headers});
  }
}
