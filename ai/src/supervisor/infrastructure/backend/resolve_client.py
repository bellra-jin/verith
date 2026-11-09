"""Strict canonical result parser only. Legacy synchronous transport is closed."""
from typing import Protocol
from src.supervisor.domain.models import CanonicalResolution

class ResolverProtocol(Protocol):
    def resolve(self,query:str):...


class ResolverToolError(RuntimeError):
    def __init__(self, kind='invalid_response', message=None):
        super().__init__('Canonical resolver unavailable')
        self.kind=kind

class StockResolverClient:
    def __init__(self,*args,**kwargs):pass
    def resolve(self,*args,**kwargs):raise ResolverToolError('backend_error')

def parse_resolution(value):
    try:return CanonicalResolution.model_validate(value)
    except (ValueError,TypeError):raise ResolverToolError() from None
