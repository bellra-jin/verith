"use client";
import {useCallback} from 'react';
import {useRouter} from 'next/navigation';
import {AnalysisEntry} from '@/features/flow/components/analysis-request';
import {SupervisorSession} from './supervisor-session';

export function SupervisorChat({supervisorId}:{supervisorId:string|null}){
 const router=useRouter();
 const navigate=useCallback((href:string,replace=false)=>replace?router.replace(href):router.push(href),[router]);
 const renderLegacy=useCallback(()=><AnalysisEntry analysisId={null}/>,[]);
 return <SupervisorSession supervisorId={supervisorId} navigate={navigate} renderLegacy={renderLegacy}/>;
}
