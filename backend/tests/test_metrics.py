from datetime import datetime, timedelta

from app.services.metrics import TripTiming, calculate_ota


SCHEDULED = datetime(2026, 9, 4, 9, 0)


def trip(delay_minutes: int) -> TripTiming:
    return TripTiming(
        scheduled_arrival=SCHEDULED,
        actual_arrival=SCHEDULED + timedelta(minutes=delay_minutes),
    )


def test_calculate_ota_treats_five_minutes_as_on_time() -> None:
    metrics = calculate_ota([trip(5)] * 8 + [trip(10)] * 2)

    assert metrics.completed_trips == 10
    assert metrics.delayed_trips == 2
    assert metrics.on_time_arrival == 80.0
    assert metrics.average_delay_minutes == 10.0


def test_calculate_ota_requires_ten_completed_trips() -> None:
    metrics = calculate_ota([trip(10)] * 9)

    assert metrics.on_time_arrival is None
    assert metrics.average_delay_minutes is None