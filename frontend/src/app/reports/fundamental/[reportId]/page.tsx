import Link from 'next/link';
import {fundamentalAnalysisEnabled} from '@/shared/server/fundamental-analysis-config';
import {FundamentalReportView} from '@/features/fundamental/components/fundamental-report-view';
import {uuid,canonicalUuid} from '@/features/fundamental/lib/analysis-request';
export const dynamic='force-dynamic';
export const revalidate=0;
export default async function FundamentalReportPage({params}:{params:Promise<{reportId:string}>}){
 const {reportId}=await params;
 if(!fundamentalAnalysisEnabled()||!uuid(reportId))return <main><p>현재 결과를 확인할 수 없습니다.</p><Link href="/">홈</Link></main>;
 return <FundamentalReportView reportId={canonicalUuid(reportId)}/>;
}
