"""One grant, fixed Backend endpoints, no environment or provider credentials."""
import asyncio
import json
from dataclasses import asdict
import httpx
from src.supervisor.domain.meaning import canonical,decode,sha
from src.supervisor.infrastructure.meaning_gateway import CounterUnavailable
from src.supervisor.infrastructure.openai_meaning_gateway import rendered_request,INPUT_FIELDS

class BackendMeaningBudget:
    def __init__(self,*,origin,service_token,grant,draft,agreement,transport=None,deadline):
        self._origin,self._token,self._grant=origin,service_token,grant
        self._draft,self._agreement,self._transport=draft,agreement,transport
        self.deadline=self.settlement_deadline=deadline
        self._hashes=None

    async def _call(self,path,value):
        started=asyncio.get_running_loop().time()
        end=min(started+5,self.settlement_deadline)
        if started>=end: raise CounterUnavailable()
        raw=canonical(value).encode()
        limit=98304 if path=='authorize' and value.get('phase')=='count' else 8192
        if len(raw)>limit: raise CounterUnavailable()
        async with asyncio.timeout_at(end):
            async with httpx.AsyncClient(transport=self._transport,trust_env=False,follow_redirects=False,verify=True,timeout=max(.001,end-started)) as client:
                async with client.stream('POST',self._origin+'/internal/supervisor/meaning/'+path,content=raw,headers={'Content-Type':'application/json','Accept-Encoding':'identity','X-Supervisor-Meaning-Service-Token':self._token,'X-Supervisor-Meaning-Grant':self._grant}) as response:
                    if response.status_code!=200 or response.headers.get('content-encoding','identity')!='identity': raise CounterUnavailable()
                    body=bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(body)+len(chunk)>8192: raise CounterUnavailable()
                        body.extend(chunk)
                    value=decode(bytes(body))
                    if type(value) is not dict: raise CounterUnavailable()
                    return value,started

    async def authorize(self,attempt_id,phase,request_hash,projection_hash,evidence):
        if phase not in {'count','generation'}: raise CounterUnavailable()
        request=rendered_request(self._draft)
        hashes=(sha(request),sha({k:request[k] for k in INPUT_FIELDS}))
        if hashes!=(request_hash,projection_hash): raise CounterUnavailable()
        agreement=asdict(self._agreement);agreement['input_fields']=list(agreement['input_fields'])
        value=dict(phase=phase,attempt_id=attempt_id,request_sha256=request_hash,projection_sha256=projection_hash,counter_sha256=sha(agreement))
        if phase=='count':
            if evidence is not None: raise CounterUnavailable()
            value['rendered_request']=request
        else:
            if self._hashes!=hashes or evidence is None: raise CounterUnavailable()
            value['evidence']=asdict(evidence)
        result,started=await self._call('authorize',value)
        if set(result)!={'newly_authorized','remaining_ms','receipt'} or type(result['newly_authorized']) is not bool or type(result['remaining_ms']) is not int or not 0<=result['remaining_ms']<=75000: raise CounterUnavailable()
        receipt=result['receipt']
        required={'phase','reservation_id','binding_sha256','request_sha256','projection_sha256','evidence_sha256'}
        if type(receipt) is not dict or set(receipt)!=required or receipt['phase']!=phase or (receipt['request_sha256'],receipt['projection_sha256'])!=hashes: raise CounterUnavailable()
        # Start at callback entry, never at receipt arrival (RTT cannot renew it).
        narrowed=started+result['remaining_ms']/1000
        self.settlement_deadline=min(self.settlement_deadline,narrowed)
        self.deadline=min(self.deadline,narrowed)
        if result['newly_authorized'] is not True or asyncio.get_running_loop().time()>=self.deadline: return False
        self._hashes=hashes
        return True

    async def reconcile(self,attempt_id,phase):
        # Explicit read-only recovery only; never automatically retry a callback
        # or turn a replay receipt into another provider dispatch.
        request=rendered_request(self._draft)
        result,_=await self._call('authorize',dict(action='reconcile',phase=phase,attempt_id=attempt_id,request_sha256=sha(request),projection_sha256=sha({k:request[k] for k in INPUT_FIELDS})))
        if result.get('newly_authorized') is not False: raise CounterUnavailable()
        return result

    async def finish(self,attempt_id,observation,*,blocked):
        if self._hashes is None:
            # An uncertain count ACK must still try to record the durable hold.
            request=rendered_request(self._draft)
            hashes=(sha(request),sha({k:request[k] for k in INPUT_FIELDS}))
        else: hashes=self._hashes
        result,_=await self._call('settle',dict(attempt_id=attempt_id,request_sha256=hashes[0],projection_sha256=hashes[1],observation=observation,blocked=blocked))
        if set(result)!={'settlement'} or type(result['settlement']) is not dict or result['settlement'].get('state') not in {'observed','unknown','anomalous'}: raise CounterUnavailable()
