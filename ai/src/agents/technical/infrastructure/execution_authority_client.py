"""One bounded authenticated HTTPS callback; no retry, proxy or key lookup."""
import asyncio
import time
import math
import ssl
import hashlib
import httpx
from src.agents.technical.domain import execution_contracts as P

def _tls_snapshot(context):
    if context is None:return None
    if (type(context) is not ssl.SSLContext or context.protocol!=ssl.PROTOCOL_TLS_CLIENT
            or context.verify_mode!=ssl.CERT_REQUIRED or context.check_hostname is not True
            or context.minimum_version<ssl.TLSVersion.TLSv1_2):raise P.ExecutionInvalid()
    return (context.minimum_version,context.maximum_version,context.verify_flags,context.options,
            tuple(sorted(hashlib.sha256(cert).hexdigest() for cert in context.get_ca_certs(binary_form=True))))

def _owned_tls(context):
    if context is None:return None
    snapshot=_tls_snapshot(context)
    certs=context.get_ca_certs(binary_form=True)
    if not certs:raise P.ExecutionInvalid()
    # Copy only explicit public CA trust into a private verifying client context.
    # Later mutation of the caller's SSLContext cannot change the handshake.
    owned=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    owned.minimum_version=context.minimum_version;owned.maximum_version=context.maximum_version
    owned.verify_flags=context.verify_flags;owned.options=context.options
    owned.load_verify_locations(cadata='\n'.join(ssl.DER_cert_to_PEM_cert(cert) for cert in certs))
    if _tls_snapshot(owned)!=snapshot:raise P.ExecutionInvalid()
    return owned

class ExecutionAuthorityClient:
    def __init__(self,*,origin,token,transport=None,tls_context=None):
        self.origin=P.origin(origin);self.token=P.service_token(token)
        if transport is not None and not isinstance(transport,httpx.AsyncBaseTransport):raise P.ExecutionInvalid()
        self.transport=transport
        self.tls_context=tls_context
        owned=_owned_tls(tls_context)
        self._configuration=(self.origin,bytes(self.token),transport,tls_context,_tls_snapshot(tls_context),owned)
    async def _post(self,path,body,grant,remaining,cap):
        P.digest(grant)
        origin,token,transport,tls_context,tls_snapshot,owned_tls=self._configuration
        P.origin(origin);P.service_token(token.decode('ascii'))
        if (self.origin!=origin or self.token!=token or self.transport is not transport
                or self.tls_context is not tls_context or _tls_snapshot(tls_context)!=tls_snapshot):raise P.ExecutionInvalid()
        if _tls_snapshot(owned_tls)!=tls_snapshot:raise P.ExecutionInvalid()
        if transport is not None and type(transport) is not httpx.ASGITransport:raise P.ExecutionInvalid()
        if type(remaining) not in (int,float) or not math.isfinite(remaining) or not 0<remaining<=86400:raise P.ExecutionInvalid()
        timeout=min(5,remaining);deadline=time.monotonic()+timeout;raw=P.canonical(body).encode('utf8')
        if len(raw)>cap:raise P.ExecutionInvalid()
        try:
            async with asyncio.timeout(timeout):
                async with httpx.AsyncClient(verify=True if owned_tls is None else owned_tls,trust_env=False,follow_redirects=False,transport=transport,timeout=timeout) as client:
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
