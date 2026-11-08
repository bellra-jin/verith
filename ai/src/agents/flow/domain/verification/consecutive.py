"""Independent latest-to-oldest evidence check. No producer or I/O imports."""
from datetime import date
import math


def verify_consecutive(values, days, signal, threshold, *, dates, subject):
    if (subject not in ("개인", "외국인", "기관") or type(values) not in (list, tuple)
            or not values or type(dates) not in (list, tuple) or len(dates) != len(values)
            or type(days) is not int or not 0 <= days <= len(values)
            or type(signal) is not bool or type(threshold) is not int or threshold < 1):
        return False
    previous = None
    for day, value in zip(dates, values):
        try:
            if (type(day) is not str or len(day) != 10 or date.fromisoformat(day).isoformat() != day
                    or previous is not None and previous >= day
                    or type(value) not in (int, float) or not math.isfinite(value)):
                return False
        except (ValueError, OverflowError, TypeError):
            return False
        previous = day
    actual = 0
    for value in reversed(values):
        if value <= 0:
            break
        actual += 1
    return days == actual and signal == (actual >= threshold)
