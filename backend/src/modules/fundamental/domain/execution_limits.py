"""Mandatory daily admission counts, independent of provider/cost accounting."""
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone, UTC
import re

MAX_LIMIT = 9223372036854775807
KST = timezone(timedelta(hours=9))


class AdmissionPolicyUnavailable(ValueError):
    def __init__(self):
        super().__init__('Fundamental admission policy unavailable')


class AdmissionLimitExceeded(ValueError):
    def __init__(self):
        super().__init__('Fundamental admission limit exceeded')


@dataclass(frozen=True, slots=True)
class AdmissionPolicy:
    user_limit: int
    service_limit: int

    def __post_init__(self):
        if (type(self.user_limit) is not int or type(self.service_limit) is not int
                or not 0 < self.user_limit <= MAX_LIMIT or not 0 < self.service_limit <= MAX_LIMIT):
            raise AdmissionPolicyUnavailable()


def policy(settings):
    """Only a new admission reads settings; missing/invalid values fail closed."""
    try:
        def number(value):
            if type(value) is int and 0 < value <= MAX_LIMIT:
                return value
            if type(value) is not str or re.fullmatch(r'[1-9][0-9]{0,18}',value) is None:
                raise AdmissionPolicyUnavailable()
            return int(value)
        return AdmissionPolicy(number(settings.FUNDAMENTAL_USER_DAILY_REQUEST_LIMIT),
                               number(settings.FUNDAMENTAL_SERVICE_DAILY_REQUEST_LIMIT))
    except (AttributeError, TypeError, ValueError):
        raise AdmissionPolicyUnavailable() from None


def period(stamp):
    if type(stamp) is not datetime or stamp.utcoffset() is None:
        raise AdmissionPolicyUnavailable()
    start=datetime.combine(stamp.astimezone(KST).date(),time(),tzinfo=KST).astimezone(UTC)
    return start,start+timedelta(days=1)
