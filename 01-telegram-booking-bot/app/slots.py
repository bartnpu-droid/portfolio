"""Free-slot calculation. Pure functions, easy to unit-test."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta


def _t(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


def free_slots(
    day: date,
    duration_min: int,
    busy: list[tuple[datetime, datetime]],
    *,
    open_time: str,
    close_time: str,
    step_min: int,
    now: datetime,
    min_lead_min: int,
    works_today: bool = True,
) -> list[datetime]:
    """Return start times where a service of `duration_min` fits completely
    inside opening hours and does not overlap any busy interval."""
    if not works_today:
        return []
    start = datetime.combine(day, _t(open_time))
    close = datetime.combine(day, _t(close_time))
    earliest = now + timedelta(minutes=min_lead_min)
    dur = timedelta(minutes=duration_min)
    step = timedelta(minutes=step_min)

    result = []
    cur = start
    while cur + dur <= close:
        end = cur + dur
        if cur >= earliest and all(end <= b_start or cur >= b_end for b_start, b_end in busy):
            result.append(cur)
        cur += step
    return result
