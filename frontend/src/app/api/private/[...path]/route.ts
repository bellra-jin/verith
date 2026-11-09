import { fundamentalAnalysisEnabled } from '@/shared/server/fundamental-analysis-config';
import { flowAnalysisEnabled } from '@/shared/server/flow-analysis-config';
import { flowDemoEnabled } from '@/shared/server/flow-demo-config';
import { sessionProxy, demoProxyError, analysisProxyError, coreProxyError } from '@/shared/server/session-proxy';
async function handle(request: Request, context:{params:Promise<{path:string[]}>}) {
  const {path}=await context.params;
  const route=path.join('/');
  if(route==='supervisor/core'||route.startsWith('supervisor/core/')){
    if(!flowAnalysisEnabled())return coreProxyError('FEATURE_UNAVAILABLE',403);
    const exact=request.method==='POST'&&['supervisor/core/prepare','supervisor/core/requests','supervisor/core/preparations'].includes(route)||request.method==='GET'&&/^supervisor\/core\/requests\/[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/.test(route)||['GET','DELETE'].includes(request.method)&&/^supervisor\/core\/preparations\/[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/.test(route);
    if(!exact||new URL(request.url).search)return coreProxyError('INPUT_INVALID',422);
    return sessionProxy(request,'/api/'+route);
  }
  if(route==='fundamental'||route.startsWith('fundamental/')){
    if(!fundamentalAnalysisEnabled())return analysisProxyError('FEATURE_UNAVAILABLE',403);
    const url=new URL(request.url),id='[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}';
    const analysis=route==='fundamental/analyses'&&request.method==='POST'||request.method==='GET'&&new RegExp('^fundamental/analyses/'+id+'$').test(route);
    const reports=route==='fundamental/reports'&&request.method==='GET'||['GET','DELETE'].includes(request.method)&&new RegExp('^fundamental/reports/'+id+'$').test(route);
    if(!analysis&&!reports||analysis&&url.search)return analysisProxyError('INPUT_INVALID',422);
    return sessionProxy(request,'/api/'+route,url.search);
  }
  if(route==='flow/plans'||route.startsWith('flow/plans/')){
    if(!flowAnalysisEnabled())return analysisProxyError('FEATURE_UNAVAILABLE',403);
    if(route!=='flow/plans'||request.method!=='POST'||new URL(request.url).search)return analysisProxyError('INPUT_INVALID',422);
    return sessionProxy(request,'/api/flow/plans');
  }
  if(route==='flow/analyses'||route.startsWith('flow/analyses/')){
    if(!flowAnalysisEnabled())return analysisProxyError('FEATURE_UNAVAILABLE',403);
    const exact=route==='flow/analyses'&&request.method==='POST'||request.method==='GET'&&/^flow\/analyses\/[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$/.test(route);
    if(!exact||new URL(request.url).search)return analysisProxyError('INPUT_INVALID',422);
    return sessionProxy(request,'/api/'+route);
  }
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
