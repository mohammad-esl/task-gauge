"""Logical-day helpers. The app's "day" runs 6:00 AM -> next 6:00 AM,
not midnight to midnight, so a late-night session counts toward the day
it started on."""
from datetime import datetime, timedelta

DAY_START_HOUR = 6


def logical_day_start(day_value):
    if isinstance(day_value, str):
        day_value = datetime.strptime(day_value, "%Y-%m-%d").date()
    return datetime.combine(day_value, datetime.min.time()) + timedelta(hours=DAY_START_HOUR)


def logical_date(dt_value):
    return (dt_value - timedelta(hours=DAY_START_HOUR)).date()


def current_logical_date_str():
    return logical_date(datetime.now()).strftime("%Y-%m-%d")


def get_hms(seconds):
    return seconds // 3600, (seconds % 3600) // 60, seconds % 60


def format_hms(seconds):
    h, m, s = get_hms(seconds)
    return f"{h:02d}:{m:02d}:{s:02d}"


def parse_hms(hms_str):
    """Inverse of format_hms; returns 0 on any malformed input."""
    try:
        h, m, s = [int(x) for x in hms_str.split(":")]
        return h * 3600 + m * 60 + s
    except Exception:
        return 0
