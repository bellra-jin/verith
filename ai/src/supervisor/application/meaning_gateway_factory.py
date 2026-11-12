"""Explicit inert options. Only a supplementing policy2 start creates a gateway."""
import re
from dataclasses import dataclass,field
from urllib.parse import urlsplit
from src.supervisor.infrastructure.meaning_gateway import CounterUnavailable

@dataclass(frozen=True,repr=False)
class MeaningRuntimeOptions:
    backend_origin: str
    service_token: str=field(repr=False)
    counter_agreement: object
    key_supplier: object=field(repr=False)
    backend_transport: object=field(default=None,repr=False)
    provider_transport: object=field(default=None,repr=False)
    allow_loopback: bool=False
    def validate(self):
        from src.supervisor.infrastructure.openai_meaning_gateway import CounterAgreement
        u=urlsplit(self.backend_origin)
        if u.scheme!='https' and not (self.allow_loopback is True and u.scheme=='http' and u.hostname in {'127.0.0.1','localhost','::1'}): raise CounterUnavailable()
        if not u.hostname or u.username or u.password or u.path not in {'','/'} or u.query or u.fragment or self.backend_origin.endswith('/'): raise CounterUnavailable()
        if type(self.service_token) is not str or not 32<=len(self.service_token)<=512 or any(not 33<=ord(c)<=126 for c in self.service_token) or not callable(self.key_supplier) or type(self.counter_agreement) is not CounterAgreement: raise CounterUnavailable()
        self.counter_agreement.validate()

class MeaningRuntime:
    def __init__(self,options):
        if type(options) is not MeaningRuntimeOptions: raise CounterUnavailable()
        options.validate();self._options=options
    def gateway(self,draft,grant,*,deadline):
        if type(grant) is not str or re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\.[0-9a-f]{64}',grant) is None: raise CounterUnavailable()
        from src.supervisor.infrastructure.backend.meaning_budget_client import BackendMeaningBudget
        from src.supervisor.infrastructure.openai_meaning_gateway import OpenAIMeaningGateway
        o=self._options
        budget=BackendMeaningBudget(origin=o.backend_origin,service_token=o.service_token,grant=grant,draft=draft,agreement=o.counter_agreement,transport=o.backend_transport,deadline=deadline)
        return OpenAIMeaningGateway(key_supplier=o.key_supplier,budget=budget,counter_agreement=o.counter_agreement,transport=o.provider_transport,deadline=deadline)
