import Link from 'next/link';
import {fundamentalAnalysisEnabled} from '@/shared/server/fundamental-analysis-config';
import {AnalysisEntry} from '@/features/fundamental/components/analysis-request';
import {uuid,canonicalUuid} from '@/features/fundamental/lib/analysis-request';

export const dynamic='force-dynamic';
export const revalidate=0;
export const metadata={title:'veriθ · 재무 분석'};
export default async function ResearchPage({searchParams}:{searchParams:Promise<Record<string,string|string[]|undefined>>}){
 if(!fundamentalAnalysisEnabled())return <main><h1>재무 분석</h1><p>현재 사용할 수 없습니다.</p><Link href="/">홈</Link></main>;
 const query=await searchParams;
 if(Object.keys(query).some(k=>k!=='analysis_id')||query.analysis_id!==undefined&&!uuid(query.analysis_id))return <main><h1>재무 분석</h1><p>잘못된 요청 주소입니다.</p><Link href="/fundamental">새 요청</Link></main>;
 return <AnalysisEntry analysisId={query.analysis_id===undefined?null:canonicalUuid(query.analysis_id)}/>;
}
