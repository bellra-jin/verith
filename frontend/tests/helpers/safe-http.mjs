// Owned production Next + synthetic Backend only. No original app/dev server adoption.
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import net from 'node:net';
import {spawn,execFileSync} from 'node:child_process';

const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
export async function listen(server,port,host){
 return new Promise((resolve,reject)=>{server.once('error',reject);server.listen(port,host,()=>{server.off('error',reject);resolve(server);});});
}
export async function reservePair(canonical=false){
 const servers=[],ports=[];
 try{
  for(const port of canonical?[3200,8200]:[0,0]){
   const server=net.createServer();servers.push(server);await listen(server,port,'127.0.0.1');ports.push(server.address().port);
   if(canonical){const ipv6=net.createServer();servers.push(ipv6);await listen(ipv6,port,'::1');}
  }
  return {ports,async close(){for(const server of servers)if(server.listening)await new Promise((resolve,reject)=>server.close(error=>error?reject(error):resolve()));}};
 }catch(error){for(const server of servers)if(server.listening)server.close();throw error;}
}
async function stopped(child){
 if(!child.pid||child.exitCode!==null||child.signalCode!==null)return;
 const group=execFileSync('/bin/ps',['-o','pgid=','-p',String(child.pid)],{env:{LANG:'en_US.UTF-8',PATH:'/usr/bin:/bin'}}).toString().trim();
 if(group!==String(process.pid))throw Error('child left owned test-worker group; not signalling');
 async function wait(){for(let n=0;n<30;n++){if(child.exitCode!==null||child.signalCode!==null)return;await delay(100);}throw Error('child did not exit');}
 child.kill('SIGTERM');try{await wait();}catch{child.kill('SIGKILL');await wait();}
}
function ownsListener(child,port){
 const output=execFileSync('/usr/sbin/lsof',['-nP','-a','-p',String(child.pid),'-iTCP:'+port,'-sTCP:LISTEN','-Fp'],{env:{LANG:'en_US.UTF-8',PATH:'/usr/bin:/bin'},timeout:2000}).toString();
 return output.split('\n').includes('p'+child.pid);
}
export function independentCleanup(steps){
 const pending=new Map(steps);let inFlight;
 return async function cleanup(){
  if(inFlight)return inFlight;
  inFlight=(async()=>{
   const errors=[];
   for(const [name,action] of [...pending]){
    try{await action();pending.delete(name);}catch(error){errors.push(new Error('Cleanup failed: '+name,{cause:error}));}
   }
   if(errors.length)throw new AggregateError(errors,'Owned cleanup incomplete');
  })();
  try{return await inFlight;}finally{inFlight=undefined;}
 };
}
export function expiryCleanup(cleanup,onFailure,milliseconds,schedule=setTimeout){
 return schedule(()=>{
  const expired=Error('Owned HTTP lifetime expired');
  Promise.resolve().then(cleanup).then(()=>onFailure(expired),error=>onFailure(new AggregateError([expired,error],'Expired with cleanup failure')));
 },milliseconds);
}
export function validateReady(proof,receipt){
 if(!receipt.alive||proof?.nonce!==receipt.nonce||proof?.pid!==receipt.pid||proof?.cwd!==receipt.cwd)throw Error('Next readiness identity mismatch');
}
export async function pollOwnedReady({alive,owns,proof,receipt,now=Date.now,sleep=delay,timeout=60000}){
 const deadline=now()+timeout;
 while(now()<deadline){
  if(!alive())throw Error('owned Next exited before ready');
  if(owns()){validateReady(await proof(),{...receipt,alive:alive()});return;}
  await sleep(Math.min(500,Math.max(0,deadline-now())));
 }
 throw Error('owned Next readiness timeout');
}
export async function ownedHTTP(handler,{canonical=false}={}){
 const filename=process.env.ST001_SAFE_CAP;
 if(!filename)throw Error('HTTP checks require the owned controller capability');
 const cap=JSON.parse(fs.readFileSync(filename,'utf8')),root=fs.realpathSync(process.cwd());
 if(root!==cap.root||!fs.existsSync(path.join(root,'.next/BUILD_ID'))||cap.ports.length!==2)throw Error('owned production build/capability missing');
 if(canonical&&(cap.ports[0]!==3200||cap.ports[1]!==8200))throw Error('canonical ports changed');
 const [port,backendPort]=cap.ports,host=canonical?'localhost':'127.0.0.1';
 const base=`http://${host}:${port}`,backendUrl=`http://${host}:${backendPort}`;
 let child,server,serverFailure,asyncFailure,expires;
 const cleanup=independentCleanup([
  ['Next child',async()=>{if(child)await stopped(child);}],
  ['Backend listener',async()=>{if(server){server.closeAllConnections();if(server.listening)await new Promise((resolve,reject)=>server.close(error=>error?reject(error):resolve()));}}],
 ]);
 async function close(){
  clearTimeout(expires);
  const errors=[];
  try{await cleanup();}catch(error){errors.push(error);}
  if(serverFailure)errors.push(serverFailure);
  if(asyncFailure)errors.push(asyncFailure);
  if(errors.length)throw new AggregateError(errors,'Owned HTTP failed/cleanup incomplete');
 }
 try{
  server=http.createServer((request,response)=>{
   if(request.url==='/__st001_health'){response.end(cap.nonce);return;}
   try{handler(request,response);}catch(error){serverFailure=error;response.statusCode=500;response.end('synthetic handler failure');}
  });
  server.on('error',error=>{serverFailure=error;});
  await listen(server,backendPort,host);
  if(server.address().port!==backendPort)throw Error('backend bind mismatch');
  const health=await fetch(backendUrl+'/__st001_health',{signal:AbortSignal.timeout(2000)});
  if(await health.text()!==cap.nonce)throw Error('backend nonce mismatch');
  // Explicit env allowlist: no spreading caller configuration into Next.
  const env={LANG:'en_US.UTF-8',TZ:'UTC',HOME:root,TMPDIR:root,PATH:'/usr/bin:/bin',NEXT_TELEMETRY_DISABLED:'1',NO_UPDATE_NOTIFIER:'1',OPENSSL_CONF:'/dev/null',
   NODE_OPTIONS:process.env.NODE_OPTIONS,ST001_SAFE_CAP:filename,NODE_ENV:'production',BACKEND_URL:backendUrl,NEXT_PUBLIC_API_URL:backendUrl,AI_SUPERVISOR_URL:backendUrl};
  child=spawn(process.execPath,[path.join(root,'node_modules/next/dist/bin/next'),'start','--hostname',host,'--port',String(port)],{cwd:root,detached:false,stdio:['ignore','pipe','pipe'],env});
  let output='';for(const stream of [child.stdout,child.stderr])stream.on('data',data=>{output=(output+data).slice(-4000);});
  let spawnError;child.once('error',error=>{spawnError=error;});
  expires=expiryCleanup(cleanup,error=>{asyncFailure=error;process.exitCode=1;},120000);expires.unref();
  await pollOwnedReady({alive:()=>!spawnError&&!asyncFailure&&child.exitCode===null&&child.signalCode===null,
   owns:()=>{try{return ownsListener(child,port);}catch{return false;}},
   proof:async()=>{const response=await fetch(base+'/__st001_ready',{signal:AbortSignal.timeout(2000)});return response.json();},
   receipt:{nonce:cap.nonce,pid:child.pid,cwd:root}});
  return {base,backendUrl,server,child,close};
 }catch(error){try{await close();}catch(cleanupError){throw new AggregateError([error,cleanupError],'Startup and cleanup failed');}throw error;}
}
