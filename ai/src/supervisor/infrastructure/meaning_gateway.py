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


class UnavailableCandidateGateway:
    async def propose(self, draft, *, attempt_id=None):
        raise MeaningUnavailable()


class CounterUnavailable(MeaningUnavailable):
    """No proved full-input mapping or counting-fee bound; sending is closed."""
