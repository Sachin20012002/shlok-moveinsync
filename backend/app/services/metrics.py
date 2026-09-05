from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class TripTiming:
    scheduled_arrival: datetime
    actual_arrival: datetime
    reported_delay_minutes: float | None = None


@dataclass(frozen=True)
class OtaMetrics:
    completed_trips: int
    delayed_trips: int
    on_time_arrival: float | None
    average_delay_minutes: float | None


def calculate_ota(
    trips: list[TripTiming],
    *,
    grace_minutes: int = 5,
    minimum_trips: int = 10,
) -> OtaMetrics:
    completed_trips = len(trips)
    delays = [
        (
            max(0.0, trip.reported_delay_minutes)
            if trip.reported_delay_minutes is not None
            else max(
                0.0,
                (trip.actual_arrival - trip.scheduled_arrival).total_seconds() / 60,
            )
        )
        for trip in trips
    ]
    delayed_trips = sum(
        delay > (0 if trip.reported_delay_minutes is not None else grace_minutes)
        for trip, delay in zip(trips, delays, strict=True)
    )

    if completed_trips < minimum_trips:
        return OtaMetrics(
            completed_trips=completed_trips,
            delayed_trips=delayed_trips,
            on_time_arrival=None,
            average_delay_minutes=None,
        )

    on_time_arrival = round(
        ((completed_trips - delayed_trips) / completed_trips) * 100,
        2,
    )
    late_delays = [
        delay
        for trip, delay in zip(trips, delays, strict=True)
        if delay > (0 if trip.reported_delay_minutes is not None else grace_minutes)
    ]
    average_delay_minutes = (
        round(sum(late_delays) / len(late_delays), 2) if late_delays else 0.0
    )

    return OtaMetrics(
        completed_trips=completed_trips,
        delayed_trips=delayed_trips,
        on_time_arrival=on_time_arrival,
        average_delay_minutes=average_delay_minutes,
    )