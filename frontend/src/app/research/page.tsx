import Link from 'next/link';
import {SupervisorChat} from '@/features/supervisor/components/supervisor-chat';
import {AppShell} from '@/shared/ui/app-shell';
import {flowAnalysisEnabled} from '@/shared/server/flow-analysis-config';
import {AnalysisEntry} from '@/features/flow/components/analysis-request';
import {uuid,canonicalUuid} from '@/features/flow/lib/analysis-request';

export const dynamic='force-dynamic';
export const revalidate=0;
export const metadata={title:'veriθ · Supervisor 리서치'};
export default async function ResearchPage({searchParams}:{searchParams:Promise<Record<string,string|string[]|undefined>>}){
 if(!flowAnalysisEnabled())return <main><h1>Flow 분석</h1><p>현재 사용할 수 없습니다.</p><Link href="/">홈</Link></main>;
 const query=await searchParams;
 if(Object.keys(query).some(k=>!['analysis_id','supervisor_id'].includes(k))||query.analysis_id!==undefined&&query.supervisor_id!==undefined||query.analysis_id!==undefined&&!uuid(query.analysis_id)||query.supervisor_id!==undefined&&!uuid(query.supervisor_id))return <main><h1>Supervisor 리서치</h1><p>잘못된 요청 주소입니다.</p><Link href="/research">새 요청</Link></main>;
 if(query.analysis_id!==undefined)return <AnalysisEntry analysisId={canonicalUuid(query.analysis_id)}/>;
 return <AppShell title="리서치 대화" subtitle="질문과 조건을 확인하고 연결된 Flow부터 실행합니다."><SupervisorChat supervisorId={query.supervisor_id===undefined?null:canonicalUuid(query.supervisor_id)}/></AppShell>;
}
