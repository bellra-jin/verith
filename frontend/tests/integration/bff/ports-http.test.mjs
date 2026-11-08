// Canonical localhost:3200 -> localhost:8200 with a synthetic backend only.
import test from 'node:test';
import assert from 'node:assert/strict';
import {request as httpRequest} from 'node:http';
import {ownedHTTP} from '../../helpers/safe-http.mjs';

function wireRequest(url,headers) {
 return new Promise((resolve,reject)=>{
  const request=httpRequest(url,{headers},response=>{
   let body='';response.setEncoding('utf8');response.on('data',chunk=>{body+=chunk;});
   response.on('end',()=>resolve(new Response(body,{status:response.statusCode,headers:response.headers})));
  });
  request.setTimeout(5000,()=>request.destroy(new Error('Synthetic local request timeout')));
  request.on('error',reject);request.end();
 });
}

test('3200 auth BFF uses fixed 8200 target and external 3200 callback; rejects aliases/Host/Origin', {timeout:120000},async()=>{
 const seen=[];
 const scope=await ownedHTTP((request,response)=>{
  seen.push({path:request.url,host:request.headers.host,cookie:request.headers.cookie});
  response.setHeader('Cache-Control','private, no-store');
  if(request.url==='/api/auth/login') {
   response.writeHead(303,{Location:'https://accounts.google.com/o/oauth2/v2/auth?redirect_uri='+encodeURIComponent('http://localhost:3200/api/auth/callback'),'Set-Cookie':'verith_login=synthetic; HttpOnly; SameSite=Lax; Path=/api/auth/callback'});response.end();
  } else if(request.url.startsWith('/api/auth/callback?')) {
   response.writeHead(303,{Location:'/','Set-Cookie':'verith_session=synthetic; HttpOnly; SameSite=Lax; Path=/'});response.end();
  } else {response.writeHead(401,{'Content-Type':'application/json'});response.end('{}');}
 },{canonical:true});
 try {
  let response=await fetch('http://localhost:3200/api/auth/login',{redirect:'manual'});
  assert.equal(response.status,303);
  assert.equal(new URL(response.headers.get('location')).searchParams.get('redirect_uri'),'http://localhost:3200/api/auth/callback');
  assert.match(response.headers.get('set-cookie'),/HttpOnly/);assert.match(response.headers.get('set-cookie'),/Path=\/api\/auth\/callback/);assert.ok(!response.headers.get('set-cookie').includes('Secure'));
  response=await fetch('http://localhost:3200/api/auth/callback?code=synthetic-code&state=synthetic-state',{headers:{Cookie:'verith_login=synthetic'},redirect:'manual'});
  assert.equal(response.status,303);assert.equal(response.headers.get('location'),'/');
  assert.ok(seen.some(row=>row.path==='/api/auth/callback?code=synthetic-code&state=synthetic-state' && row.host==='localhost:8200' && row.cookie==='verith_login=synthetic'));
  const before=seen.length;
  for(const headers of [{Host:'evil.unit'},{Host:'localhost:3000'},{Host:'localhost:3201'},{Host:'127.0.0.1:3200'},{'X-Forwarded-Host':'evil.unit'},{Origin:'http://localhost:3000'},{Origin:'http://localhost:3201'},{Origin:'http://127.0.0.1:3200'}]) {
   response=await wireRequest('http://localhost:3200/api/auth/session',headers);
   assert.equal(response.status,403,JSON.stringify(headers));
   assert.equal(response.headers.get('cache-control'),'private, no-store');
  }
  assert.equal(seen.length,before,'rejected local auth requests must not reach upstream');
  const rejectedSSR=await wireRequest('http://localhost:3200/',{Host:'evil.unit',Cookie:'verith_session=synthetic'});
  assert.equal(rejectedSSR.status,200);
  assert.equal(seen.length,before,'spoofed SSR Host must not fetch private Backend data');
  response=await fetch('http://localhost:3200/api/supervisor/analyze',{method:'POST'});assert.equal(response.status,403);
  response=await fetch('http://localhost:3200/api/flow/reports',{method:'POST'});assert.equal(response.status,403);
  assert.equal(seen.length,before,'forbidden analysis/save upstream must stay zero');
 } finally {
  await scope.close();
 }
});
