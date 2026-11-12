"""One bounded authenticated HTTPS callback; no retry, proxy or key lookup."""
import asyncio
import time
import math
import httpx
from src.agents.technical.domain import execution_contracts as P

class ExecutionAuthorityClient:
    def __init__(self,*,origin,token,transport=None):
        self.origin=P.origin(origin);self.token=P.service_token(token)
        if transport is not None and not isinstance(transport,httpx.AsyncBaseTransport):raise P.ExecutionInvalid()
        self.transport=transport
        self._configuration=(self.origin,bytes(self.token),transport)
    async def _post(self,path,body,grant,remaining,cap):
        P.digest(grant)
        origin,token,transport=self._configuration
        P.origin(origin);P.service_token(token.decode('ascii'))
        if self.origin!=origin or self.token!=token or self.transport is not transport:raise P.ExecutionInvalid()
        if transport is not None and type(transport) is not httpx.ASGITransport:raise P.ExecutionInvalid()
        if type(remaining) not in (int,float) or not math.isfinite(remaining) or not 0<remaining<=86400:raise P.ExecutionInvalid()
        timeout=min(5,remaining);deadline=time.monotonic()+timeout;raw=P.canonical(body).encode('utf8')
        if len(raw)>cap:raise P.ExecutionInvalid()
        try:
            async with asyncio.timeout(timeout):
                async with httpx.AsyncClient(verify=True,trust_env=False,follow_redirects=False,transport=transport,timeout=timeout) as client:
                    async with client.stream('POST',origin+path,content=raw,headers={'Content-Type':'application/json','Accept':'application/json','Accept-Encoding':'identity','X-Technical-Authority-Token':token.decode('ascii'),'X-Technical-Execution-Grant':grant}) as response:
                        if response.status_code!=200 or response.headers.get('content-encoding','identity')!='identity':raise P.ExecutionInvalid()
                        value=bytearray()
                        async for chunk in response.aiter_bytes():
                            if len(value)+len(chunk)>cap:raise P.ExecutionInvalid()
                            value.extend(chunk)
                        parsed=P.decode(value,cap)
                        if time.monotonic()>=deadline:raise P.ExecutionInvalid()
            if time.monotonic()>=deadline:raise P.ExecutionInvalid()
            return parsed
        except asyncio.CancelledError:raise
        except Exception:raise P.ExecutionInvalid() from None
    async def start(self,execution,grant,executor_id,remaining):
        deadline=time.monotonic()+min(5,remaining)
        body={'schema_version':P.SCHEMA,'analysis_id':execution['control']['analysis_id'],'control_sha256':execution['control_sha256'],'executor_id':executor_id}
        value=await self._post('/internal/technical/execution/start',body,grant,remaining,8192)
        parsed=P.check_start(value,execution['control_sha256'],executor_id)
        if time.monotonic()>=deadline:raise P.ExecutionInvalid()
        return parsed
    async def observe(self,execution,grant,start,evidence,remaining):
        body={'schema_version':P.SCHEMA,'analysis_id':execution['control']['analysis_id'],'control_sha256':execution['control_sha256'],'executor_id':start['executor_id'],'start_sha256':start['start_sha256'],'evidence':evidence,'evidence_sha256':P.sha(P.canonical(evidence))}
        value=await self._post('/internal/technical/execution/observe',body,grant,remaining,16384)
        if value!={'schema_version':P.SCHEMA,'recorded':True,'analysis_id':body['analysis_id'],'evidence_sha256':body['evidence_sha256']}:raise P.ExecutionInvalid()
        return value
