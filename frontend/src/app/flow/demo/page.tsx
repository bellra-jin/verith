import Link from 'next/link';
import { flowDemoEnabled } from '@/shared/server/flow-demo-config';
import { sessionBackendFetch } from '@/shared/server/session-backend';
import { sessionValue, wireView, uuid, canonicalUuid, type DemoView } from '@/features/flow/lib/synthetic-demo';
import { SyntheticDemo } from '@/features/flow/components/synthetic-demo';

export const dynamic='force-dynamic';
export const revalidate=0;
export default async function DemoPage({searchParams}:{searchParams:Promise<Record<string,string|string[]|undefined>>}) {
 if(!flowDemoEnabled())return <main><h1>Flow 합성 데모</h1><p>현재 사용할 수 없습니다.</p><Link href="/">홈</Link></main>;
 const query=await searchParams;
 if(Object.keys(query).some(k=>k!=='run_id')||query.run_id!==undefined&&!uuid(query.run_id))return <main><h1>Flow 합성 데모</h1><p>잘못된 데모 주소입니다.</p><Link href="/flow/demo">요청 화면</Link></main>;
 let loaded:{userId:string;id:string|null;view:DemoView|null}|null=null;
 let loginRequired=false;
 try {
  const response=await sessionBackendFetch('/api/auth/session');
  if(!response?.ok)loginRequired=true;
  else {
  const session=sessionValue(await response.json());
  if(!session)throw Error('Invalid session');
  const id=query.run_id===undefined?null:canonicalUuid(query.run_id);
  let view:DemoView|null=null;
  if(id!==null){
   const result=await sessionBackendFetch('/api/flow/synthetic-demo/runs/'+id);
   if(result?.ok){view=await wireView(result,session.user_id);if(view.run_id!==id)view=null;}
  }
  loaded={userId:session.user_id,id,view};
  }
 }catch{loaded=null;}
 if(loginRequired)return <main><h1>Flow 합성 데모</h1><p>로그인 후 이용하세요.</p><Link href="/api/auth/login">로그인</Link></main>;
 if(!loaded)return <main><h1>Flow 합성 데모</h1><p>데모 요청을 확인할 수 없습니다.</p><Link href="/">홈</Link></main>;
 return <SyntheticDemo key={loaded.userId+':'+(loaded.id ?? 'new')} userId={loaded.userId} runId={loaded.id} initialView={loaded.view}/>;
}
