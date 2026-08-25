from datetime import datetime

import time_utils


def test_logical_date_before_6am_counts_as_previous_day():
    dt = datetime(2026, 8, 7, 3, 21)
    assert time_utils.logical_date(dt).isoformat() == "2026-08-06"


def test_logical_date_after_6am_counts_as_same_day():
    dt = datetime(2026, 8, 6, 7, 41)
    assert time_utils.logical_date(dt).isoformat() == "2026-08-06"


def test_logical_date_at_exactly_6am_counts_as_same_day():
    dt = datetime(2026, 8, 6, 6, 0, 0)
    assert time_utils.logical_date(dt).isoformat() == "2026-08-06"


def test_logical_day_start_from_string():
    start = time_utils.logical_day_start("2026-08-06")
    assert start == datetime(2026, 8, 6, 6, 0, 0)


def test_get_hms():
    assert time_utils.get_hms(3661) == (1, 1, 1)
    assert time_utils.get_hms(0) == (0, 0, 0)


def test_format_hms():
    assert time_utils.format_hms(3661) == "01:01:01"
    assert time_utils.format_hms(0) == "00:00:00"


def test_parse_hms_roundtrip():
    assert time_utils.parse_hms("13:47:07") == 13 * 3600 + 47 * 60 + 7


def test_parse_hms_malformed_returns_zero():
    assert time_utils.parse_hms("") == 0
    assert time_utils.parse_hms("not a time") == 0
