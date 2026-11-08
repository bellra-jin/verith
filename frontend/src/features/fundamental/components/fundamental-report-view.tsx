'use client';
import {useEffect,useRef,useState} from 'react';
import {getFundamentalReport,type FundamentalReportEnvelope} from '../api/reports';
import {storedUuid,displayValue,fetchSession,safeSourceUrl} from '../lib/analysis-request';
import {FundamentalActions} from './fundamental-actions';
const record=(v:unknown):v is Record<string,unknown>=>v!==null&&typeof v==='object'&&!Array.isArray(v);
function rows(v:unknown):Record<string,unknown>[]{return Array.isArray(v)?v.filter(record):[];}
export function FundamentalReportView({reportId}:{reportId:string}){
 const [value,setValue]=useState<FundamentalReportEnvelope|null>(null);const [error,setError]=useState('');const generation=useRef(0);
 useEffect(()=>{let active=true;let controller:AbortController|null=null;let timer:ReturnType<typeof setTimeout>|null=null;
  const invalidate=()=>{generation.current++;controller?.abort();setValue(null);};
  async function read(){generation.current++;controller?.abort();const revision=generation.current;controller=new AbortController();const signal=controller.signal;timer=setTimeout(()=>controller?.abort(),15000);
   try{const before=await fetchSession(signal);const result=await getFundamentalReport(reportId,signal);const after=await fetchSession(signal);if(before.user_id!==after.user_id)throw Error();if(active&&revision===generation.current&&!signal.aborted){setValue(result);setError('');}}
   catch{if(active&&revision===generation.current)setError('본인 결과를 확인할 수 없습니다. 로그인과 요청 주소를 확인하세요.');}finally{if(timer)clearTimeout(timer);}
  }
  const visibility=()=>{if(document.visibilityState==='hidden')invalidate();else void read();};
  const hide=()=>invalidate();const show=()=>{if(document.visibilityState!=='hidden')void read();};
  document.addEventListener('visibilitychange',visibility);window.addEventListener('pagehide',hide);window.addEventListener('pageshow',show);void read();
  return()=>{active=false;invalidate();if(timer)clearTimeout(timer);document.removeEventListener('visibilitychange',visibility);window.removeEventListener('pagehide',hide);window.removeEventListener('pageshow',show);};
 },[reportId]);
 if(!value)return <main><h1>재무 결과</h1><p role="status">{error||'본인 결과를 확인 중입니다.'}</p></main>;
 const raw=value.report,meta=record(raw.meta)?raw.meta:{},erd=record(meta.erd_payload)?meta.erd_payload:{},root=record(erd.fundamental_report)?erd.fundamental_report:{};
 if(storedUuid(root.id)!==value.report_id)return <p>저장 결과를 확인할 수 없습니다.</p>;
 const interpretation=record(erd.report_interpretation)?erd.report_interpretation:{};
 return <main><h1>{displayValue(raw.corp_name)} 재무 결과</h1><FundamentalActions reportId={value.report_id}/>
  <p>저장된 원본 해석입니다. 실제 공급자와 재무 품질은 미검증이며 과거 시점 분석을 보장하지 않습니다.</p>
  <dl><dt>종목</dt><dd>{displayValue(raw.ticker)}</dd><dt>점수</dt><dd>{displayValue(raw.score)}</dd><dt>판정</dt><dd>{displayValue(raw.verdict)}</dd><dt>데이터 상태</dt><dd>{displayValue(root.data_status)}</dd><dt>자료 기준일 (요청 시각과 다름)</dt><dd>{displayValue(root.as_of)}</dd><dt>재무 기간</dt><dd>{displayValue(root.period_label)}</dd></dl>
  <h2>해석 원문</h2><p style={{whiteSpace:'pre-wrap'}}>{displayValue(interpretation.interpretation)}</p>
  <h2>지표</h2><ul>{rows(erd.report_ratios).map((row,i)=><li key={i}>{displayValue(row.label)}: {displayValue(row.display_value??row.value)} {displayValue(row.unit)} · {displayValue(row.status)} · {displayValue(row.reason)}</li>)}</ul>
  <h2>근거·출처</h2><ul>{rows(erd.report_evidence).map((row,i)=>{const url=safeSourceUrl(row.source_url);return <li key={i}>{displayValue(row.claim)} · {displayValue(row.display_value??row.amount)} {displayValue(row.unit)} · {url?<a href={url} target="_blank" rel="noreferrer noopener">출처</a>:<span>{displayValue(row.source_url)}</span>}</li>;})}</ul>
  <h2>공시 발췌</h2><ul>{rows(erd.report_filing_snippets).map((row,i)=><li key={i}>{displayValue(row.section_name)} · {displayValue(row.snippet)}</li>)}</ul>
 </main>;
}
