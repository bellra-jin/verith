import { sessionProxy } from '@/shared/server/session-proxy';
async function handle(request: Request, context:{params:Promise<{path:string[]}>}) {
  const {path}=await context.params;
  const route=path.join('/');
  const detail=/^flow\/reports\/[0-9a-fA-F-]{36}$/.test(route);
  if (!(request.method==='GET' && ['flow/reports','reports','reports/archive'].includes(route) || detail && ['GET','DELETE'].includes(request.method))) return new Response(null,{status:403,headers:{'Cache-Control':'private, no-store'}});
  const query=new URLSearchParams();
  for (const [key,value] of new URL(request.url).searchParams) {
    if (['agent_type','stock_code','limit','offset'].includes(key)) query.append(key,value);
  }
  return sessionProxy(request,'/api/'+route,query.size ? '?'+query.toString() : '');
}
export {handle as GET,handle as DELETE};
