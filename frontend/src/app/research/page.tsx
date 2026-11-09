import Link from 'next/link';
import {flowAnalysisEnabled} from '@/shared/server/flow-analysis-config';
import {AnalysisEntry} from '@/features/flow/components/analysis-request';
import {uuid,canonicalUuid} from '@/features/flow/lib/analysis-request';

export const dynamic='force-dynamic';
export const revalidate=0;
export const metadata={title:'veriθ · 자연어 Flow 준비'};
export default async function ResearchPage({searchParams}:{searchParams:Promise<Record<string,string|string[]|undefined>>}){
 if(!flowAnalysisEnabled())return <main><h1>Flow 분석</h1><p>현재 사용할 수 없습니다.</p><Link href="/">홈</Link></main>;
 const query=await searchParams;
 if(Object.keys(query).some(k=>k!=='analysis_id')||query.analysis_id!==undefined&&!uuid(query.analysis_id))return <main><h1>Flow 분석</h1><p>잘못된 요청 주소입니다.</p><Link href="/research">새 요청</Link></main>;
 return <AnalysisEntry analysisId={query.analysis_id===undefined?null:canonicalUuid(query.analysis_id)}/>;
}
