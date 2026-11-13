"""Explicit request-local graph assembly. Import/default registration has no SDK/graph/key I/O."""
import asyncio
from dataclasses import dataclass,fields
from datetime import datetime,UTC
import inspect
import math
import os
import time
import threading
from uuid import UUID,uuid4
from src.agents.technical.domain import execution_contracts as P

@dataclass(frozen=True,slots=True,repr=False)
class ExecutionOptions:
    configuration:P.Configuration
    service_token:str
    authority_token:str
    credential_supplier:object
    fetcher:object
    cache:object
    trace_sink:object
    fetcher_stop:object=None
    authority_tls_context:object=None

class TechnicalProviderRuntime:
    def __init__(self,options,*,agent_module,steps_module,llm_module,authority):
        if type(options) is not ExecutionOptions or type(options.configuration) is not P.Configuration:raise P.ExecutionInvalid()
        self.configuration=P.Configuration(options.configuration.text)
        self._configuration_text=self.configuration.text;self._options=options;self._steps_module=steps_module
        self._fetcher_stop=options.fetcher_stop
        self.service_token=P.service_token(options.service_token)
        self.authority_token=P.service_token(options.authority_token)
        if self.service_token==self.authority_token:raise P.ExecutionInvalid()
        self.options=options;self.agent_module=agent_module;self.steps_module=steps_module;self.llm_module=llm_module;self.authority=authority
        self.runner=agent_module.run_technical_agent;self.factory=llm_module.official_count_openai_client
        self.policy_type=llm_module.TechnicalLlmPolicy;self.budget_type=llm_module.TechnicalRequestLlmBudget
        self._capabilities=(self.runner,self.factory,self.policy_type,self.budget_type)
        self.authority_start=authority.start;self.authority_observe=authority.observe
        self.authority_snapshot=(authority.origin,bytes(authority.token),authority.transport)
        self._check()
    def _check(self):
        cfg=self.configuration.data();o=self.options
        def sync(value):return callable(value) and not inspect.iscoroutinefunction(value) and not inspect.iscoroutinefunction(getattr(value,'__call__',None))
        for name in ('LANGCHAIN_TRACING','LANGCHAIN_TRACING_V2','LANGSMITH_TRACING','LANGSMITH_TRACING_V2'):
            value=os.environ.get(name)
            if value is not None and value.lower() not in {'false','0'}:raise P.ExecutionInvalid()
        self._authority_check()
        if (self.configuration.text!=self._configuration_text or self.options is not self._options or self.steps_module is not self._steps_module
                or any(left is not right for left,right in zip((self.runner,self.factory,self.policy_type,self.budget_type),self._capabilities))
                or self.agent_module.run_technical_agent is not self.runner or self.llm_module.official_count_openai_client is not self.factory
                or self.llm_module.TechnicalLlmPolicy is not self.policy_type or self.llm_module.TechnicalRequestLlmBudget is not self.budget_type
                or self.steps_module.INTRADAY_FETCH_ENABLED is not False
                or o.fetcher_stop is not self._fetcher_stop
                or o.fetcher_stop is not None and (type(o.fetcher_stop) is not threading.Event or o.fetcher_stop.is_set())
                or not sync(self.runner) or not sync(self.factory) or not sync(o.fetcher) or not sync(o.credential_supplier)
                or not isinstance(self.policy_type,type) or not isinstance(self.budget_type,type)
                or o.cache is not None and not all(sync(getattr(o.cache,k,None)) for k in ('get','set'))
                or o.trace_sink is not None and not sync(getattr(o.trace_sink,'emit',None))
                or (cfg['cache_mode']=='none')!=(o.cache is None) or (cfg['trace_mode']=='none')!=(o.trace_sink is None)):
            raise P.ExecutionInvalid()
        # No default minute/name fetcher, cache, trace or credential is constructed.
        return cfg
    def _authority_check(self):
        origin,token,transport=self.authority_snapshot
        def same(left,right):return getattr(left,'__self__',None) is getattr(right,'__self__',None) and getattr(left,'__func__',None) is getattr(right,'__func__',None) and getattr(left,'__func__',None) is not None
        if (origin!=P.Configuration(self._configuration_text).data()['authority_origin'] or token!=self.authority_token or self.authority.origin!=origin or self.authority.token!=token or self.authority.transport is not transport
                or getattr(self.authority,'tls_context',None) is not self.options.authority_tls_context
                or not same(self.authority.start,self.authority_start) or not same(self.authority.observe,self.authority_observe)):raise P.ExecutionInvalid()
    def readiness(self):
        cfg=self._check()
        return {'schema_version':P.SCHEMA,'configuration':cfg,'spec_sha256':P.SPEC_SHA256,'ready':True}
    async def execute(self,value,grant):
        from src.agents.technical.application.boundary_runtime import controlled_slot
        from src.shared.runtime.deadline import Deadline
        configuration=P.Configuration(self._configuration_text)
        P.parse_execution(value,configuration);P.digest(grant);self._check()
        # Snapshot before first await, including all meaning/config/control bytes.
        text=P.canonical(value);value=P.decode(text);control=value['control'];boundary=value['boundary_request']
        if not boundary['data']['stock']['stock_name']:raise P.ExecutionInvalid()
        from src.agents.technical.application.boundary_adapter import project_input
        payload=project_input(boundary)  # existing strict planning, before start/credential
        anchor=time.monotonic();now=datetime.now(UTC)
        remaining=min((P.stamp(control['deadline_at'])-now).total_seconds(),(P.stamp(control['deadline_at'])-P.stamp(control['started_at'])).total_seconds())
        if not math.isfinite(remaining) or remaining<=0:raise P.ExecutionInvalid()
        deadline=Deadline(anchor+remaining);executor_id=str(uuid4());state={'cancelled':False,'budget':None,'reason':None}
        fetcher_stop=self._fetcher_stop
        def close_pending(reason='CLOSED'):
            state['cancelled']=True;state['reason']=reason
            if fetcher_stop is not None:fetcher_stop.set()
            if state['budget'] is not None:state['budget']._close(reason)
        async def work():
            nonlocal deadline
            self._check();deadline.check('technical_start')
            start_anchor=time.monotonic()
            start=await self.authority_start(value,grant,executor_id,deadline.remaining_seconds())
            P.check_start(start,value['control_sha256'],executor_id)
            if start['newly_started'] is not True:raise P.ExecutionInvalid()
            server_start=P.stamp(start['started_at'])
            server_remaining=(P.stamp(control['deadline_at'])-server_start).total_seconds()
            if server_start<P.stamp(control['started_at']) or server_remaining<=0:raise P.ExecutionInvalid()
            # Anchor before the callback, include its complete elapsed time, and
            # only narrow the ingress deadline using the authoritative DB clock.
            deadline=Deadline(min(deadline.expires_at,start_anchor+server_remaining))
            # This ACK is consumed only by this work, never cached/replayed.
            cfg=configuration.data();p=cfg['policy'];adapter=None;budget=None;outcome='failed';result=None
            try:
                self._check();deadline.check('technical_after_start')
                if state['cancelled']:raise P.ExecutionInvalid()
                policy=self.policy_type(policy_json=P.canonical(p),policy_sha256=control['policy_sha256'],**{f.name:p[f.name] for f in fields(self.policy_type) if f.name not in {'policy_json','policy_sha256'}})
                budget=self.budget_type(policy=policy,analysis_id=UUID(control['analysis_id']),attempt_id=UUID(control['attempt_id']),reserved_nano=control['reserved_nano'],started_at=P.stamp(control['started_at']),deadline_at=P.stamp(control['deadline_at']))
                # Further narrow the budget's independent wall-clock projection.
                budget._monotonic_deadline=min(budget._monotonic_deadline,deadline.expires_at)
                state['budget']=budget
                if state['cancelled']:budget._close('DEADLINE_EXCEEDED');raise P.ExecutionInvalid()
                credential=self.options.credential_supplier()  # first key access, after fresh start ACK only
                adapter=self.factory(request_budget=budget,api_key=credential,request_wire_cap=cfg['caps']['request'],count_wire_cap=cfg['caps']['count'],generation_wire_cap=cfg['caps']['generation'],count_version=cfg['counter']['version'],count_provenance_sha256=cfg['counter']['provenance_sha256'],timeout=deadline.remaining_seconds(),deadline=deadline)
                del credential
                from src.agents.technical.application.engine_bridge import TechnicalEngineBridge
                def checked_runner(payload,**kwargs):
                    self._check()
                    return self.runner(payload,**kwargs)
                bridge=TechnicalEngineBridge(sync_runner=checked_runner,llm_client=adapter,fetcher=self.options.fetcher,cache=self.options.cache,trace_sink=self.options.trace_sink,enabled=True,deadline=deadline,controlled=True,on_cancel=lambda:close_pending('CLOSED'))
                output=await bridge(payload,trace_id=boundary['trace_id'])
                deadline.check('technical_execution_result')
                result=P.result(boundary,output,{'control_sha256':value['control_sha256'],'start_sha256':start['start_sha256'],'executor_id':executor_id});outcome='completed'
            except asyncio.CancelledError:
                if budget is not None:budget._close('CLOSED')
                # Bridge waits for its physical thread; actual task cancellation
                # does not create a detached observation or retry.
                raise
            except Exception:
                outcome='deadline' if deadline.expired() or state['reason']=='DEADLINE_EXCEEDED' else 'cancelled' if state['cancelled'] else 'failed'
                if budget is not None:budget._close('CLOSED')
            finally:
                if fetcher_stop is not None:fetcher_stop.set()
                if adapter is not None:
                    try:adapter.close()
                    except Exception:pass
            records=[]
            for item in (() if budget is None else budget.snapshot()):
                records.append({f.name:(str(getattr(item,f.name)) if isinstance(getattr(item,f.name),UUID) else list(getattr(item,f.name)) if type(getattr(item,f.name)) is tuple else getattr(item,f.name)) for f in fields(item)})
            evidence={'schema_version':'technical.usage.v1','analysis_id':control['analysis_id'],'attempt_id':control['attempt_id'],'policy_sha256':control['policy_sha256'],'control_sha256':value['control_sha256'],'start_sha256':start['start_sha256'],'executor_id':executor_id,'outcome':outcome,'records':records}
            P.evidence(evidence,configuration,control,start)
            try:
                self._authority_check()
                await self.authority_observe(value,grant,start,evidence,max(0.001,min(5,deadline.remaining_seconds())) if not deadline.expired() else 5)
            except asyncio.CancelledError:raise
            except Exception:pass  # Result acceptance and usage ACK are independent; full hold remains.
            if result is None:raise P.ExecutionInvalid()
            return result
        return await controlled_slot(work,remaining=deadline.remaining_seconds(),close_pending=close_pending)

def install_runtime(options,*,authority_transport=None):
    # Only an explicit installation imports real graph/SDK dependencies.
    from src.agents.technical.application import agent
    from src.agents.technical.application.orchestration import pipeline_steps
    from src.agents.technical.infrastructure import openai_llm_client
    from src.agents.technical.infrastructure.execution_authority_client import ExecutionAuthorityClient
    authority=ExecutionAuthorityClient(origin=options.configuration.data()['authority_origin'],token=options.authority_token,transport=authority_transport,tls_context=options.authority_tls_context)
    return TechnicalProviderRuntime(options,agent_module=agent,steps_module=pipeline_steps,llm_module=openai_llm_client,authority=authority)
