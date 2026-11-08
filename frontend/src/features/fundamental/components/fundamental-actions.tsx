'use client';
import Link from 'next/link';
import {useRef,useState} from 'react';
import {useRouter} from 'next/navigation';
import {deleteFundamentalReport} from '../api/reports';
export function FundamentalActions({reportId}:{reportId:string}){
 const router=useRouter();const busy=useRef(false);const [pending,setPending]=useState(false);const [error,setError]=useState('');
 async function remove(){if(busy.current||!window.confirm('이 본인 결과를 삭제할까요?'))return;busy.current=true;setPending(true);try{await deleteFundamentalReport(reportId);router.replace('/fundamental');router.refresh();}catch{busy.current=false;setPending(false);setError('삭제 결과를 확인할 수 없습니다.');}}
 return <nav><Link href="/fundamental">본인 재무 목록</Link><button disabled={pending} onClick={()=>void remove()}>{pending?'삭제 중':'개별 삭제'}</button>{error&&<p role="alert">{error}</p>}</nav>;
}
