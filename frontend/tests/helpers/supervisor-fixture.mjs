// Fixture-only URL/adapter/lifecycle. No production state or credentials.
export function validateFixtureTarget(target){
 const invalid={status:422,kind:'invalid',id:null};
 if(typeof target!=='string'||new TextEncoder().encode(target).length>2048||!target.startsWith('/')||target.startsWith('//')||/[\x00-\x20\x7f\\#%]/.test(target)||target.split(/[/?]/).some(p=>p==='.'||p==='..'))return invalid;
 const [pathname,query,...extra]=target.split('?');
 if(pathname!=='/research')return {status:target.includes('?')?422:404,kind:'other',id:null};
 if(extra.length)return invalid;
 if(query===undefined)return {status:200,kind:'research',id:null};
 const match=/^supervisor_id=([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})$/i.exec(query);
 return match?{status:200,kind:'research',id:match[1].toLowerCase()}:invalid;
}
export function fixtureAdapter({origin,location,history,events,onChange,onInvalid,onOutside}){
 const read=()=>validateFixtureTarget(location.pathname+location.search+location.hash);
 const apply=()=>{const parsed=read();if(parsed.status!==200){onInvalid();return;}onChange(parsed.id);};
 return {initial:read(),navigate(href,replace=false){
  if(typeof href!=='string'){onInvalid();return;}
  const raw=href.startsWith(origin+'/')?href.slice(origin.length):href;
  const parsed=validateFixtureTarget(raw);
  if(parsed.status!==200){if(parsed.kind==='other'&&raw.startsWith('/reports/flow/')&&!raw.includes('?'))onOutside();else onInvalid();return;}
  history[replace?'replaceState':'pushState']({},'',raw);onChange(parsed.id);
 },listen(){events.addEventListener('popstate',apply);apply();return ()=>events.removeEventListener('popstate',apply);}};
}
export const browserNotExecuted=()=>Object.fromEntries(['react_mount','interaction','storage_navigation','visual_1440','visual_390','focus'].map(k=>[k,'not_executed']));
export function terminalAction(raw){
 // An exact lexical shape also rejects duplicate JSON keys without accepting JSON.parse's last key.
 if(typeof raw!=='string'||!/^\s*\{\s*"action"\s*:\s*"(?:complete|cancel)"\s*\}\s*$/.test(raw))throw Error('Fixture terminal body invalid');
 return JSON.parse(raw).action;
}
export function createFixtureTerminal({stopWork,drain,writeReceipt,ack,close,settled=()=>{}}){
 let phase='open';
 return {get phase(){return phase;},open(){return phase==='open';},async finish(action){
  if(!['complete','cancel','timed_out','failed'].includes(action))throw Error('Fixture terminal action invalid');
  if(phase!=='open')throw Error('Fixture terminal conflict');
  phase='closing';stopWork();
  try{
   await drain();
   const state={complete:'completed',cancel:'cancelled',timed_out:'timed_out',failed:'failed'}[action];
   const receipt=await writeReceipt({action,state});
   await ack(receipt);await close();phase=state;settled();return receipt;
  }catch(error){phase='failed';await close();throw error;}
 }};
}
export function validateTerminalReceipt(receipt,proof){
 const keys=['schema','nonce','pid','cwd','port','action','state','counts','browser'];
 const counters=['sessionGET','preparePOST','prepareGET','prepareDELETE','confirmPOST','outcomeGET','model','provider'];
 if(!receipt||typeof receipt!=='object'||Array.isArray(receipt)||Object.keys(receipt).sort().join()!==keys.sort().join()||receipt.schema!=='cf025.terminal.v1'||!['nonce','pid','cwd','port'].every(k=>receipt[k]===proof[k])||!['complete','cancel','timed_out','failed'].includes(receipt.action)||receipt.state!=={complete:'completed',cancel:'cancelled',timed_out:'timed_out',failed:'failed'}[receipt.action]||!receipt.counts||Object.keys(receipt.counts).sort().join()!==counters.sort().join()||counters.some(k=>!Number.isSafeInteger(receipt.counts[k])||receipt.counts[k]<0)||receipt.counts.model!==0||receipt.counts.provider!==0||JSON.stringify(receipt.browser)!==JSON.stringify(browserNotExecuted()))throw Error('Fixture terminal receipt mismatch');
 return receipt;
}
// Parent callback boundary: ACK loss is never retried or called ACK success.
export async function collectFixtureTerminal({probe,child,readReceipt,proof,postcheck,stop=async()=>{},onReceipt=()=>{}}){
 let stopping;
 const failed=async error=>{stopping??=Promise.resolve().then(stop);await stopping;throw error;};
 const results=await Promise.allSettled([probe.catch(failed),child.catch(failed)]);
 await postcheck();
 const receipt=validateTerminalReceipt(await readReceipt(),proof);onReceipt(receipt);
 if(results[1].status!=='fulfilled')throw Error('Fixture child settlement failed');
 if(results[0].status!=='fulfilled')throw Error('Fixture probe failed; terminal receipt retained as evidence');
 const observation=results[0].value;
 if(!['received','unknown'].includes(observation.ack)||observation.action!==receipt.action||JSON.stringify(observation.counts)!==JSON.stringify(receipt.counts))throw Error('Fixture probe/terminal evidence mismatch');
 return {ack:observation.ack,receipt,http:observation.http,browser:browserNotExecuted()};
}

export class FixtureProtocolError extends Error{constructor(){super('Fixture response protocol invalid');this.code='CF025_PROTOCOL_INVALID';}}
export async function terminalAcknowledgement(send,action){
 let response;
 try{response=await send();}catch(error){if(error?.code==='CF025_PROTOCOL_INVALID')throw Error('Fixture terminal ACK invalid');return {ack:'unknown'};}
 // A received negative/malformed ACK is a known failure, never an unknown ACK.
 if(response.status!==200)throw Error('Fixture terminal ACK invalid');
 let value;try{value=response.json();}catch{throw Error('Fixture terminal ACK invalid');}
 if(!value||Object.keys(value).join()!=='state'||value.state!==(action==='complete'?'completed':'cancelled'))throw Error('Fixture terminal ACK invalid');
 return {ack:'received'};
}
