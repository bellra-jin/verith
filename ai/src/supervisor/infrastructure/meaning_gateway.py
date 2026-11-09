"""Typed extraction gateway; production has no SDK/config and is unavailable."""
from typing import Protocol

class MeaningUnavailable(RuntimeError):
    pass

class MeaningGateway(Protocol):

    async def extract(self, draft) -> dict:
        ...

class UnavailableMeaningGateway:

    async def extract(self, draft):
        raise MeaningUnavailable('Meaning extraction unavailable')
