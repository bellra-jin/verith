// Actual Next SSR/BFF with a synthetic HTTP backend only; no Google/DB/AI.
import test from 'node:test';
import assert from 'node:assert/strict';
import {ownedHTTP} from '../../helpers/safe-http.mjs';

test('Next SSR preserves duplicate cookies; archive pages and deletion return remain reachable', {timeout:120000}, async()=>{
 let total=25;
 const observed=[];
 const scope=await ownedHTTP((request,response)=>{
  const url=new URL(request.url,'http://synthetic.unit');
  const cookie=request.headers.cookie ?? '';
  observed.push({path:url.pathname,query:url.search,cookie});
  const tokens=cookie.split(';').map(part=>part.trim()).filter(part=>part.startsWith('verith_session='));
  response.setHeader('Content-Type','application/json');
  response.setHeader('Cache-Control','private, no-store');
  if(tokens.length!==1 || tokens[0]!=='verith_session=valid-B') {response.writeHead(401);response.end('{}');return;}
  if(url.pathname==='/api/auth/session') {response.end(JSON.stringify({csrf_token:'synthetic-csrf'}));return;}
  if(url.pathname==='/api/reports/archive') {
   assert.equal(url.searchParams.get('agent_type'),'flow');
   const limit=Number(url.searchParams.get('limit')),offset=Number(url.searchParams.get('offset'));
   assert.ok(Number.isSafeInteger(limit) && limit>=1 && limit<=100 && Number.isSafeInteger(offset) && offset>=0);
   const items=Array.from({length:Math.max(0,Math.min(limit,total-offset))},(_,index)=>{
    const number=offset+index+1;
    return {report_id:`00000000-0000-4000-8000-${String(number).padStart(12,'0')}`,stock:{stock_name:`fixture-${String(number).padStart(2,'0')}`},card:{title:'synthetic-only'}};
   });
   response.end(JSON.stringify({total,items}));return;
  }
  if(request.method==='DELETE' && url.pathname.startsWith('/api/flow/reports/')) {
   assert.equal(request.headers['x-csrf-token'],'synthetic-csrf');
   total--;
   response.writeHead(204);response.end();return;
  }
  response.writeHead(404);response.end('{}');
 });
 const base=scope.base;
 const valid={Cookie:'verith_session=valid-B'};
 try {
  for(const cookie of ['verith_session=expired; verith_session=valid-B','verith_session=valid-B; verith_session=expired']) {
   const response=await fetch(base,{headers:{Cookie:cookie}});
   const html=await response.text();
   assert.ok(!html.includes('내 Flow 보관함'));
   assert.ok(html.includes('Google로 로그인'));
   assert.equal((await fetch(base+'/api/auth/session',{headers:{Cookie:cookie}})).status,401);
   assert.ok(observed.filter(row=>row.cookie===cookie && row.path==='/api/auth/session').length>=2,'SSR and BFF must preserve both raw cookie orders');
  }
  let response=await fetch(base,{headers:valid});let html=await response.text();
  assert.match(html,/fixture-01/);assert.match(html,/fixture-20/);assert.ok(!html.includes('fixture-21'));
  assert.match(html,/다음 페이지/);assert.ok(!html.includes('이전 페이지'));
  assert.ok(html.includes('/?limit=20&amp;offset=20'));
  response=await fetch(base+'/?limit=20&offset=20',{headers:valid});html=await response.text();
  assert.match(html,/fixture-21/);assert.match(html,/fixture-25/);assert.ok(!html.includes('fixture-01'));
  assert.match(html,/이전 페이지/);assert.ok(!html.includes('다음 페이지'));
  assert.ok(html.includes('00000000-0000-4000-8000-000000000021?limit=20&amp;offset=20'));
  for(const query of ['?limit=-1&offset=-1','?limit=NaN&offset=NaN','?limit=999999999999999999999999&offset=999999999999999999999999','?limit=1&limit=2&offset=1&offset=2']) {
   await fetch(base+'/'+query,{headers:valid});
   const last=observed.filter(row=>row.path==='/api/reports/archive').at(-1);
   assert.equal(last.query,'?agent_type=flow&limit=20&offset=0');
  }
  total=21;
  const deleted=await fetch(base+'/api/private/flow/reports/00000000-0000-4000-8000-000000000021',{method:'DELETE',headers:{...valid,'X-CSRF-Token':'synthetic-csrf',Origin:base}});
  assert.equal(deleted.status,204);
  response=await fetch(base+'/?limit=20&offset=20',{headers:valid});
  assert.equal(new URL(response.url).search,'?limit=20&offset=0');
  assert.match(await response.text(),/fixture-20/);
  total=0;
  response=await fetch(base+'/?limit=20&offset=20',{headers:valid});
  html=await response.text();
  assert.equal(new URL(response.url).search,'?limit=20&offset=0');
  assert.match(html,/저장된 본인 결과가 없습니다/);
  assert.ok(!html.includes('이전 페이지') && !html.includes('다음 페이지'));
  assert.ok(observed.every(row=>row.path==='/api/auth/session' || row.path==='/api/reports/archive' || row.path.startsWith('/api/flow/reports/')));
 } finally {
  await scope.close();
 }
});
