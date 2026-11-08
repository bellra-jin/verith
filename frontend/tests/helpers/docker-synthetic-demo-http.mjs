// CF010 Docker-only adapter: never loaded by the Mac protected entry.
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import net from 'node:net';
import {spawn} from 'node:child_process';
import {randomBytes} from 'node:crypto';
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function bind(server,port,host){await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(port,host,()=>{server.off('error',reject);resolve();});});}
async function reservations(canonical){
 const servers=[],ports=[];
 try{
  for(const port of canonical?[3200,8200]:[0,0]){
   const server=net.createServer();servers.push(server);await bind(server,port,'127.0.0.1');ports.push(server.address().port);
   if(canonical){const ipv6=net.createServer();servers.push(ipv6);await bind(ipv6,port,'::1');}
  }
  if(ports[0]===ports[1])throw Error('CF010 port collision');
  return {ports,async close(){for(const s of servers)if(s.listening)await new Promise((resolve,reject)=>s.close(error=>error?reject(error):resolve()));}};
 }catch(error){for(const s of servers)if(s.listening)s.close();throw error;}
}
function listenerOwned(child,port){
 if(!child.pid||child.exitCode!==null||child.signalCode!==null)return false;
 const sockets=new Set();
 for(const fd of fs.readdirSync('/proc/'+child.pid+'/fd')){
  try{const match=/^socket:\[(\d+)\]$/.exec(fs.readlinkSync('/proc/'+child.pid+'/fd/'+fd));if(match)sockets.add(match[1]);}catch(error){if(error.code!=='ENOENT')throw error;}
 }
 for(const table of ['tcp','tcp6'])for(const line of fs.readFileSync('/proc/net/'+table,'utf8').trim().split('\n').slice(1)){
  const fields=line.trim().split(/\s+/);
  if(fields[3]==='0A'&&parseInt(fields[1].split(':')[1],16)===port&&sockets.has(fields[9]))return true;
 }
 return false;
}
export async function ownedHTTP(handler,{canonical=false,demo=false}={}){
 if(typeof canonical!=='boolean'||typeof demo!=='boolean')throw Error('CF010 fixed boolean required');
 const root=fs.realpathSync(process.cwd());
 if(root!=='/work'||process.getuid()!==1000||process.getgid()!==1000)throw Error('CF010 owned root/user required');
 for(const file of ['.cf010-owner.json','.next/BUILD_ID']){const s=fs.lstatSync(path.join(root,file));if(!s.isFile()||s.nlink!==1||s.uid!==1000)throw Error('CF010 owned proof required');}
 const marker=JSON.parse(fs.readFileSync('.cf010-owner.json','utf8'));
 if(Object.keys(marker).sort().join(',')!=='nonce,owner,root,schema'||marker.schema!==1||marker.root!==root||marker.owner!==process.env.CF010_OWNER||!/^cf010-[a-f0-9]{24}$/.test(marker.owner)||!/^[a-f0-9]{64}$/.test(marker.nonce)||!fs.readFileSync('.next/BUILD_ID','utf8').trim())throw Error('CF010 ownership mismatch');
 let reserved,server,child,lifetime,failure,closing;
 async function stopChild(){
  if(!child?.pid||child.exitCode!==null||child.signalCode!==null)return;
  child.kill('SIGTERM');
  for(let i=0;i<30&&child.exitCode===null&&child.signalCode===null;i++)await delay(100);
  if(child.exitCode===null&&child.signalCode===null){child.kill('SIGKILL');for(let i=0;i<20&&child.exitCode===null&&child.signalCode===null;i++)await delay(100);}
  if(child.exitCode===null&&child.signalCode===null)throw Error('CF010 child cleanup incomplete');
 }
 async function close(){
  if(closing)return closing;
  closing=(async()=>{
   clearTimeout(lifetime);const errors=[];
   for(const action of [stopChild,async()=>{if(server){server.closeAllConnections();if(server.listening)await new Promise((resolve,reject)=>server.close(error=>error?reject(error):resolve()));}},async()=>{await reserved?.close();}]){
    try{await action();}catch(error){errors.push(error);}
   }
   if(failure)errors.push(failure);
   if(errors.length)throw new AggregateError(errors,'CF010 owned HTTP failed/cleanup incomplete');
  })();return closing;
 }
 const nonce=randomBytes(32).toString('hex');
 try{
  reserved=await reservations(canonical);const [port,backendPort]=reserved.ports;
  const host=canonical?'localhost':'127.0.0.1',base=`http://${host}:${port}`,backendUrl=`http://${host}:${backendPort}`;
  await reserved.close();
  server=http.createServer((request,response)=>{
   if(request.url==='/cf010-upstream-ready'){response.end(nonce);return;}
   try{handler(request,response);}catch(error){failure=error;response.writeHead(500);response.end('synthetic handler failure');}
  });
  server.on('error',error=>{failure=error;});await bind(server,backendPort,host);
  if(server.address().port!==backendPort)throw Error('CF010 backend port mismatch');
  const health=await fetch(backendUrl+'/cf010-upstream-ready',{signal:AbortSignal.timeout(2000)});
  if(await health.text()!==nonce)throw Error('CF010 upstream proof mismatch');
  const env={PATH:'/usr/local/bin:/usr/bin:/bin',HOME:'/tmp/home',TMPDIR:'/tmp',TZ:'UTC',LANG:'C.UTF-8',OPENSSL_CONF:'/dev/null',NEXT_TELEMETRY_DISABLED:'1',NODE_ENV:'production',BACKEND_URL:backendUrl,NEXT_PUBLIC_API_URL:backendUrl,AI_SUPERVISOR_URL:backendUrl,FLOW_SYNTHETIC_DEMO_ENABLED:demo?'true':'false',CF010_READY_NONCE:nonce};
  child=spawn(process.execPath,[path.join(root,'node_modules/next/dist/bin/next'),'start','--hostname',host,'--port',String(port)],{cwd:root,env,stdio:['ignore','pipe','pipe'],detached:false});
  let output='';for(const stream of [child.stdout,child.stderr])stream.on('data',bytes=>{output=(output+bytes).slice(-4000);});
  child.once('error',error=>{failure=error;});
  lifetime=setTimeout(()=>{failure=Error('CF010 case lifetime expired');close().catch(()=>{});process.exitCode=1;},120000);lifetime.unref();
  const deadline=Date.now()+60000;
  while(Date.now()<deadline){
   if(failure||child.exitCode!==null||child.signalCode!==null)throw failure||Error('CF010 Next exited before ready: '+output);
   if(listenerOwned(child,port)){
    const response=await fetch(base+'/cf010-ready',{signal:AbortSignal.timeout(2000)});const proof=await response.json();
    if(response.status!==200||proof.nonce!==nonce||proof.pid!==child.pid||proof.cwd!==root||!listenerOwned(child,port))throw Error('CF010 Next readiness identity mismatch');
    return {base,backendUrl,server,child,close};
   }
   await delay(100);
  }
  throw Error('CF010 readiness timeout');
 }catch(error){try{await close();}catch(cleanup){throw new AggregateError([error,cleanup],'CF010 startup/cleanup failed');}throw error;}
}
