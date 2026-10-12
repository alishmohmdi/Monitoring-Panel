from datetime import (
    datetime,
    time,
    timedelta,
    timezone,
)

from zoneinfo import ZoneInfo


# =========================================================
# CONFIG
# =========================================================

BUSINESS_TIMEZONE = ZoneInfo(
    "Asia/Tehran"
)

BUSINESS_START_HOUR = 10
BUSINESS_END_HOUR = 17

SLA_SECONDS = 2 * 60 * 60


# =========================================================
# TIME HELPERS
# =========================================================

def utc_now_naive() -> datetime:
    """
    Database currently stores naive UTC datetimes.
    """

    return (
        datetime
        .now(timezone.utc)
        .replace(tzinfo=None)
    )


def utc_naive_to_tehran(
    value: datetime,
) -> datetime:

    if value.tzinfo is None:

        value = value.replace(
            tzinfo=timezone.utc
        )

    return value.astimezone(
        BUSINESS_TIMEZONE
    )


def tehran_to_utc_naive(
    value: datetime,
) -> datetime:

    if value.tzinfo is None:

        value = value.replace(
            tzinfo=BUSINESS_TIMEZONE
        )

    return (
        value
        .astimezone(timezone.utc)
        .replace(tzinfo=None)
    )


def tehran_now() -> datetime:

    return datetime.now(
        BUSINESS_TIMEZONE
    )


# =========================================================
# BUSINESS WINDOW
# =========================================================

def business_start(
    value: datetime,
) -> datetime:

    return value.replace(
        hour=BUSINESS_START_HOUR,
        minute=0,
        second=0,
        microsecond=0,
    )


def business_end(
    value: datetime,
) -> datetime:

    return value.replace(
        hour=BUSINESS_END_HOUR,
        minute=0,
        second=0,
        microsecond=0,
    )


def is_business_time(
    value: datetime | None = None,
) -> bool:

    if value is None:

        value = tehran_now()

    if value.tzinfo is None:

        value = value.replace(
            tzinfo=BUSINESS_TIMEZONE
        )

    start = business_start(
        value
    )

    end = business_end(
        value
    )

    return (
        start
        <= value
        < end
    )


# =========================================================
# NEXT BUSINESS START
# =========================================================

def next_business_start(
    value: datetime | None = None,
) -> datetime:

    if value is None:

        value = tehran_now()

    if value.tzinfo is None:

        value = value.replace(
            tzinfo=BUSINESS_TIMEZONE
        )

    start = business_start(
        value
    )

    end = business_end(
        value
    )

    # قبل از 10 صبح
    if value < start:

        return start

    # داخل ساعت کاری
    if value < end:

        return value

    # بعد از 17
    tomorrow = (
        value
        + timedelta(days=1)
    )

    return business_start(
        tomorrow
    )


# =========================================================
# BUSINESS-TIME SLA
# =========================================================

def add_business_seconds(
    started_at_utc: datetime,
    seconds: int = SLA_SECONDS,
) -> datetime:
    """
    Add only working-time seconds.

    Example:
    Start 16:30 Tehran
    + 2 business hours
    => next day 11:30 Tehran
    """

    current = utc_naive_to_tehran(
        started_at_utc
    )

    current = next_business_start(
        current
    )

    remaining = seconds


    while remaining > 0:

        end = business_end(
            current
        )

        available = int(
            (
                end - current
            ).total_seconds()
        )

        if remaining <= available:

            current = (
                current
                + timedelta(
                    seconds=remaining
                )
            )

            remaining = 0

            break


        remaining -= available

        next_day = (
            current
            + timedelta(days=1)
        )

        current = business_start(
            next_day
        )


    return tehran_to_utc_naive(
        current
    )


def remaining_business_seconds(
    deadline_utc: datetime | None,
) -> int | None:

    if deadline_utc is None:

        return None


    now_tehran = tehran_now()

    deadline_tehran = (
        utc_naive_to_tehran(
            deadline_utc
        )
    )


    if (
        now_tehran
        >= deadline_tehran
    ):

        return 0


    current = now_tehran
    remaining = 0


    while current.date() <= deadline_tehran.date():

        start = business_start(
            current
        )

        end = business_end(
            current
        )


        if (
            current.date()
            ==
            now_tehran.date()
        ):

            interval_start = max(
                current,
                start,
            )

        else:

            interval_start = start


        if (
            current.date()
            ==
            deadline_tehran.date()
        ):

            interval_end = min(
                deadline_tehran,
                end,
            )

        else:

            interval_end = end


        if (
            interval_end
            >
            interval_start
        ):

            remaining += int(
                (
                    interval_end
                    - interval_start
                ).total_seconds()
            )


        current = business_start(
            current
            + timedelta(days=1)
        )


    return max(
        0,
        remaining,
    )