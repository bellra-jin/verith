import {canonicalUuid,fetchSession} from '../lib/analysis-request';
export type FundamentalReportEnvelope={report_id:string;report:Record<string,unknown>};
export async function getFundamentalReport(reportId:string,signal?:AbortSignal):Promise<FundamentalReportEnvelope>{
 const id=canonicalUuid(reportId);const response=await fetch('/api/private/fundamental/reports/'+id,{cache:'no-store',signal:signal??AbortSignal.timeout(15000)});
 if(!response.ok)throw Error('본인 결과를 확인할 수 없습니다.');const raw:unknown=await response.json();
 if(typeof raw!=='object'||raw===null)throw Error('저장 결과가 잘못됐습니다.');const v=raw as Record<string,unknown>;
 if(typeof v.report_id!=='string'||canonicalUuid(v.report_id)!==id||typeof v.report!=='object'||v.report===null||Array.isArray(v.report))throw Error('저장 결과가 잘못됐습니다.');
 return {report_id:id,report:v.report as Record<string,unknown>};
}
export async function deleteFundamentalReport(reportId:string):Promise<void>{
 const signal=AbortSignal.timeout(15000);const session=await fetchSession(signal);
 const response=await fetch('/api/private/fundamental/reports/'+canonicalUuid(reportId),{method:'DELETE',headers:{'X-CSRF-Token':session.csrf_token},cache:'no-store',signal});
 if(response.status!==204)throw Error('본인 결과를 삭제할 수 없습니다.');
}
export async function deleteAllFundamentalReports():Promise<never>{throw Error('전체 삭제는 지원하지 않습니다.');}
