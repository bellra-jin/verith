import { sessionProxy } from '@/lib/session-proxy';
export async function GET(request: Request, context: {params:Promise<{action:string}>}) {
  const {action}=await context.params;
  if (!['login','callback','session'].includes(action)) return new Response(null,{status:404});
  return sessionProxy(request,`/api/auth/${action}`,action==='callback' ? new URL(request.url).search : '');
}
export async function POST(request: Request, context: {params:Promise<{action:string}>}) {
  const {action}=await context.params;
  if (action!=='logout') return new Response(null,{status:404});
  return sessionProxy(request,'/api/auth/logout');
}
