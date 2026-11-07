'use client';
import {useState} from 'react';
export function SessionControls({csrfToken, reportId, returnTo="/"}:{csrfToken:string;reportId?:string;returnTo?:string}) {
  const [error,setError]=useState('');
  async function act() {
    try {
      const response=await fetch(reportId ? `/api/private/flow/reports/${reportId}` : '/api/auth/logout',{method:reportId ? 'DELETE' : 'POST',headers:{'X-CSRF-Token':csrfToken},cache:'no-store'});
      if (!response.ok) {setError('요청을 처리할 수 없습니다. 다시 로그인해 주세요.');return;}
      window.location.assign(reportId ? returnTo : '/');
    } catch {setError('요청을 처리할 수 없습니다.');}
  }
  return <div><button type="button" onClick={act}>{reportId ? '이 결과 삭제' : '로그아웃'}</button>{error && <p role="alert">{error}</p>}</div>;
}
