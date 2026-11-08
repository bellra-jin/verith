import { flowDemoEnabled } from '@/shared/server/flow-demo-config';
import { sessionProxy, demoProxyError } from '@/shared/server/session-proxy';
async function handle(request: Request, context:{params:Promise<{path:string[]}>}) {
  const {path}=await context.params;
  const route=path.join('/');
  if(route==='flow/synthetic-demo/runs' || route.startsWith('flow/synthetic-demo/runs/')) {
    if(!flowDemoEnabled())return demoProxyError('FEATURE_UNAVAILABLE',403);
    const exact=route==='flow/synthetic-demo/runs' && request.method==='POST' || request.method==='GET' && /^flow\/synthetic-demo\/runs\/[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$/.test(route);
    if(!exact)return demoProxyError('FEATURE_UNAVAILABLE',403);
    if(new URL(request.url).search)return demoProxyError('INPUT_INVALID',422);
    return sessionProxy(request,'/api/'+route);
  }
  const detail=/^flow\/reports\/[0-9a-fA-F-]{36}$/.test(route);
  if (!(request.method==='GET' && ['flow/reports','reports','reports/archive'].includes(route) || detail && ['GET','DELETE'].includes(request.method))) return new Response(null,{status:403,headers:{'Cache-Control':'private, no-store'}});
  const query=new URLSearchParams();
  for (const [key,value] of new URL(request.url).searchParams) {
    if (['agent_type','stock_code','limit','offset'].includes(key)) query.append(key,value);
  }
  return sessionProxy(request,'/api/'+route,query.size ? '?'+query.toString() : '');
}
export {handle as GET,handle as DELETE,handle as POST};
