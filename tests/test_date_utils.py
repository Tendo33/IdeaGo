"""Tests for date_utils module.

测试日期时间工具函数模块。
"""

from datetime import datetime, timedelta, timezone

import python_template.utils.date_utils as date_utils_module
from python_template.utils.date_utils import (
    add_days,
    add_hours,
    add_minutes,
    format_datetime,
    from_unix_timestamp,
    get_current_date,
    get_current_time,
    get_month_start,
    get_time_difference,
    get_timestamp,
    get_unix_timestamp,
    get_week_start,
    humanize_timedelta,
    is_weekend,
    parse_datetime,
    parse_timestamp,
)


class TestTimestamp:
    """Tests for timestamp functions."""

    def test_get_timestamp_with_timezone(self) -> None:
        """Test getting timestamp with timezone."""
        result = get_timestamp(include_timezone=True)
        assert "+" in result or "Z" in result or "-" in result[-6:]
        # Verify it's a valid ISO format
        assert "T" in result

    def test_get_timestamp_without_timezone(self) -> None:
        """Test getting timestamp without timezone."""
        result = get_timestamp(include_timezone=False)
        assert "T" in result

    def test_parse_timestamp_valid(self) -> None:
        """Test parsing valid timestamp."""
        timestamp = "2024-06-15T14:30:45+00:00"
        result = parse_timestamp(timestamp)
        assert result is not None
        assert result.year == 2024
        assert result.month == 6
        assert result.day == 15

    def test_parse_timestamp_invalid(self) -> None:
        """Test parsing invalid timestamp returns None."""
        result = parse_timestamp("invalid-timestamp")
        assert result is None


class TestFormatParseDatetime:
    """Tests for format_datetime and parse_datetime functions."""

    def test_format_datetime_default(self, sample_datetime: datetime) -> None:
        """Test default datetime formatting."""
        result = format_datetime(sample_datetime)
        assert result == "2024-06-15 14:30:45"

    def test_format_datetime_custom(self, sample_datetime: datetime) -> None:
        """Test custom datetime formatting."""
        result = format_datetime(sample_datetime, format_str="%Y/%m/%d")
        assert result == "2024/06/15"

    def test_parse_datetime_valid(self) -> None:
        """Test parsing valid datetime string."""
        result = parse_datetime("2024-06-15 14:30:45")
        assert result is not None
        assert result.year == 2024
        assert result.hour == 14

    def test_parse_datetime_invalid(self) -> None:
        """Test parsing invalid datetime returns None."""
        result = parse_datetime("invalid-date")
        assert result is None


class TestCurrentDateTime:
    """Tests for get_current_date and get_current_time functions."""

    def test_get_current_date_format(self) -> None:
        """Test current date format."""
        result = get_current_date()
        # Should be in YYYY-MM-DD format
        assert len(result) == 10
        assert result[4] == "-"
        assert result[7] == "-"

    def test_get_current_time_format(self) -> None:
        """Test current time format."""
        result = get_current_time()
        # Should be in HH:MM:SS format
        assert len(result) == 8
        assert result[2] == ":"
        assert result[5] == ":"

    def test_get_current_date_defaults_to_utc(self, monkeypatch) -> None:
        """Default current date should be produced from UTC now()."""

        class FixedDateTime(datetime):
            @classmethod
            def now(cls, tz=None):  # noqa: ANN001
                if tz is timezone.utc:
                    return cls(2026, 2, 20, 0, 30, 0, tzinfo=timezone.utc)
                return cls(2026, 2, 19, 16, 30, 0)

        monkeypatch.setattr(date_utils_module, "datetime", FixedDateTime)
        assert get_current_date() == "2026-02-20"
        assert get_current_date(use_utc=False) == "2026-02-19"

    def test_get_current_time_defaults_to_utc(self, monkeypatch) -> None:
        """Default current time should be produced from UTC now()."""

        class FixedDateTime(datetime):
            @classmethod
            def now(cls, tz=None):  # noqa: ANN001
                if tz is timezone.utc:
                    return cls(2026, 2, 20, 0, 30, 1, tzinfo=timezone.utc)
                return cls(2026, 2, 19, 16, 30, 2)

        monkeypatch.setattr(date_utils_module, "datetime", FixedDateTime)
        assert get_current_time() == "00:30:01"
        assert get_current_time(use_utc=False) == "16:30:02"


class TestAddTime:
    """Tests for add_days, add_hours, add_minutes functions."""

    def test_add_days_positive(self, sample_datetime: datetime) -> None:
        """Test adding positive days."""
        result = add_days(sample_datetime, 5)
        assert result.day == 20

    def test_add_days_negative(self, sample_datetime: datetime) -> None:
        """Test adding negative days."""
        result = add_days(sample_datetime, -5)
        assert result.day == 10

    def test_add_hours(self, sample_datetime: datetime) -> None:
        """Test adding hours."""
        result = add_hours(sample_datetime, 3)
        assert result.hour == 17

    def test_add_minutes(self, sample_datetime: datetime) -> None:
        """Test adding minutes."""
        result = add_minutes(sample_datetime, 45)
        assert result.hour == 15
        assert result.minute == 15


class TestTimeDifference:
    """Tests for get_time_difference function."""

    def test_time_difference_seconds(self) -> None:
        """Test time difference in seconds."""
        dt1 = datetime(2024, 1, 1, 10, 0, 0)
        dt2 = datetime(2024, 1, 1, 10, 1, 30)
        result = get_time_difference(dt1, dt2, unit="seconds")
        assert result == 90

    def test_time_difference_minutes(self) -> None:
        """Test time difference in minutes."""
        dt1 = datetime(2024, 1, 1, 10, 0, 0)
        dt2 = datetime(2024, 1, 1, 10, 30, 0)
        result = get_time_difference(dt1, dt2, unit="minutes")
        assert result == 30

    def test_time_difference_hours(self) -> None:
        """Test time difference in hours."""
        dt1 = datetime(2024, 1, 1, 10, 0, 0)
        dt2 = datetime(2024, 1, 1, 13, 0, 0)
        result = get_time_difference(dt1, dt2, unit="hours")
        assert result == 3

    def test_time_difference_days(self) -> None:
        """Test time difference in days."""
        dt1 = datetime(2024, 1, 1)
        dt2 = datetime(2024, 1, 8)
        result = get_time_difference(dt1, dt2, unit="days")
        assert result == 7


class TestWeekendAndPeriods:
    """Tests for is_weekend, get_week_start, get_month_start functions."""

    def test_is_weekend_saturday(self) -> None:
        """Test Saturday is weekend."""
        saturday = datetime(2024, 6, 15)  # 2024-06-15 is Saturday
        assert is_weekend(saturday) is True

    def test_is_weekend_weekday(self) -> None:
        """Test weekday is not weekend."""
        monday = datetime(2024, 6, 17)  # 2024-06-17 is Monday
        assert is_weekend(monday) is False

    def test_get_week_start(self) -> None:
        """Test getting week start (Monday)."""
        wednesday = datetime(2024, 6, 19, 15, 30)  # Wednesday
        result = get_week_start(wednesday)
        assert result.weekday() == 0  # Monday
        assert result.hour == 0
        assert result.minute == 0

    def test_get_month_start(self) -> None:
        """Test getting month start."""
        mid_month = datetime(2024, 6, 15, 15, 30)
        result = get_month_start(mid_month)
        assert result.day == 1
        assert result.hour == 0
        assert result.minute == 0


class TestHumanizeTimedelta:
    """Tests for humanize_timedelta function."""

    def test_humanize_seconds(self) -> None:
        """Test humanizing seconds."""
        result = humanize_timedelta(90)
        assert "1 minute" in result
        assert "30 seconds" in result

    def test_humanize_hours(self) -> None:
        """Test humanizing hours."""
        result = humanize_timedelta(3661)  # 1 hour, 1 minute, 1 second
        assert "1 hour" in result

    def test_humanize_days(self) -> None:
        """Test humanizing days."""
        result = humanize_timedelta(timedelta(days=2, hours=3))
        assert "2 days" in result


class TestUnixTimestamp:
    """Tests for Unix timestamp functions."""

    def test_get_unix_timestamp(self, sample_datetime: datetime) -> None:
        """Test getting Unix timestamp."""
        result = get_unix_timestamp(sample_datetime)
        assert isinstance(result, int)
        assert result > 0

    def test_from_unix_timestamp(self) -> None:
        """Test creating datetime from Unix timestamp."""
        timestamp = 1718457045  # 2024-06-15 14:30:45 UTC
        result = from_unix_timestamp(timestamp)
        assert isinstance(result, datetime)

    def test_unix_timestamp_roundtrip(self, sample_datetime: datetime) -> None:
        """Test Unix timestamp roundtrip."""
        timestamp = get_unix_timestamp(sample_datetime)
        result = from_unix_timestamp(timestamp)
        assert result.year == sample_datetime.year
        assert result.month == sample_datetime.month
        assert result.day == sample_datetime.day
