from datetime import date, datetime, time, timedelta, timezone
from math import sqrt
import asyncio
import os
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware


BASE = os.getenv(
    "ELEXON_API_BASE",
    "https://data.elexon.co.uk/bmrs/api/v1",
).rstrip("/")

CUTOFF_HOUR = max(
    0,
    min(23, int(os.getenv("DAY_AHEAD_CUTOFF_HOUR_UTC", "23"))),
)

app = FastAPI(
    title="Gridbricks Wind Intelligence API",
    version="1.0.2",
    description="Day-ahead wind forecast accuracy analysis.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def pick(row: dict[str, Any], *keys):
    lowered = {str(key).lower(): value for key, value in row.items()}

    for key in keys:
        value = lowered.get(key.lower())
        if value is not None:
            return value

    return None


def dtparse(value):
    if value is None:
        return None

    value = str(value).strip()

    if not value:
        return None

    if value.endswith("Z"):
        value = value[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def number(value):
    try:
        result = float(value)

        if result != result or abs(result) == float("inf"):
            return None

        return result

    except (TypeError, ValueError):
        return None


def settlement_timestamp(row):
    settlement_date = pick(
        row, "settlementDate", "settlement_date"
    )
    settlement_period = number(
        pick(row, "settlementPeriod", "settlement_period")
    )

    if settlement_date is None or settlement_period is None:
        return None

    try:
        day = date.fromisoformat(str(settlement_date)[:10])
        period = int(settlement_period)

        if not 1 <= period <= 50:
            return None

        return (
            datetime.combine(day, time.min, tzinfo=timezone.utc)
            + timedelta(minutes=(period - 1) * 30)
        )

    except (ValueError, TypeError):
        return None


def actual_timestamp(row):
    timestamp = dtparse(
        pick(
            row,
            "startTime",
            "start_time",
            "settlementTime",
            "settlement_time",
            "datetime",
        )
    )

    return timestamp or settlement_timestamp(row)


def forecast_timestamp(row):
    timestamp = settlement_timestamp(row)

    if timestamp is not None:
        return timestamp

    timestamp = dtparse(
        pick(
            row,
            "deliveryStartTime",
            "delivery_start_time",
            "targetTime",
            "target_time",
        )
    )

    if timestamp is not None:
        return timestamp

    return dtparse(
        pick(row, "startTime", "start_time", "datetime")
    )


def norm_forecasts(rows):
    normalized = []

    for row in rows:
        timestamp = forecast_timestamp(row)

        value = number(
            pick(
                row,
                "generation",
                "generationMW",
                "generation_mw",
                "quantity",
                "value",
                "windGeneration",
                "windGenerationMW",
            )
        )

        published = dtparse(
            pick(
                row,
                "publishTime",
                "publish_time",
                "publicationTime",
                "publication_time",
            )
        )

        if timestamp is not None and value is not None:
            normalized.append(
                {
                    "timestamp": timestamp,
                    "forecast_mw": value,
                    "published_at": published,
                }
            )

    return normalized


def norm_actuals(rows):
    normalized = []

    accepted_wind_types = {
        "wind",
        "wind offshore",
        "wind onshore",
        "windoffshore",
        "windonshore",
        "wind_offshore",
        "wind_onshore",
    }

    for row in rows:
        fuel = pick(
            row,
            "fuelType",
            "fuel_type",
            "fuel",
            "psrType",
            "psr_type",
        )

        if (
            fuel is not None
            and str(fuel).strip().lower() not in accepted_wind_types
        ):
            continue

        timestamp = actual_timestamp(row)

        value = number(
            pick(
                row,
                "generation",
                "generationMW",
                "generation_mw",
                "quantity",
                "value",
            )
        )

        if timestamp is not None and value is not None:
            normalized.append(
                {
                    "timestamp": timestamp,
                    "actual_mw": value,
                }
            )

    return normalized


def select_forecasts(rows, start, end):
    """
    Select one forecast per delivery timestamp.

    A forecast is eligible only when it was published by the configured
    UTC cutoff on the calendar day before its delivery date.
    """
    selected = {}

    for row in rows:
        timestamp = row["timestamp"]
        published = row["published_at"]

        if published is None:
            continue

        if not (start <= timestamp.date() <= end):
            continue

        cutoff_date = timestamp.date() - timedelta(days=1)

        cutoff = datetime.combine(
            cutoff_date,
            time(
                hour=CUTOFF_HOUR,
                minute=59,
                second=59,
                tzinfo=timezone.utc,
            ),
        )

        if published > cutoff:
            continue

        previous = selected.get(timestamp)

        if (
            previous is None
            or published > previous["published_at"]
        ):
            selected[timestamp] = row

    return selected


def metrics(records, actual_count):
    if not records:
        return {
            "matched_intervals": 0,
            "actual_intervals": actual_count,
            "coverage_pct": 0,
            "mae_mw": None,
            "rmse_mw": None,
            "wape_pct": None,
            "bias_mw": None,
        }

    errors = [
        row["forecast_mw"] - row["actual_mw"]
        for row in records
    ]

    absolute_errors = [abs(error) for error in errors]

    total_actual = sum(
        abs(row["actual_mw"]) for row in records
    )

    return {
        "matched_intervals": len(records),
        "actual_intervals": actual_count,
        "coverage_pct": round(
            len(records) / actual_count * 100, 2
        ) if actual_count else 0,
        "mae_mw": round(
            sum(absolute_errors) / len(absolute_errors), 3
        ),
        "rmse_mw": round(
            sqrt(
                sum(error * error for error in errors)
                / len(errors)
            ),
            3,
        ),
        "wape_pct": round(
            sum(absolute_errors) / total_actual * 100, 3
        ) if total_actual else None,
        "bias_mw": round(
            sum(errors) / len(errors), 3
        ),
    }


def analyze(forecast_rows, actual_rows, from_date, to_date):
    normalized_forecasts = norm_forecasts(forecast_rows)

    selected_forecasts = select_forecasts(
        normalized_forecasts,
        from_date,
        to_date,
    )

    normalized_actuals = norm_actuals(actual_rows)

    # Keep actual observations within the requested delivery dates.
    normalized_actuals = [
        row for row in normalized_actuals
        if from_date <= row["timestamp"].date() <= to_date
    ]

    # Aggregate half-hourly actual readings into hourly averages.
    hourly_actuals = {}

    for row in normalized_actuals:
        timestamp = row["timestamp"]
        hour = timestamp.replace(
            minute=0,
            second=0,
            microsecond=0,
        )

        bucket = hourly_actuals.setdefault(
            hour,
            {"total": 0.0, "count": 0},
        )

        bucket["total"] += row["actual_mw"]
        bucket["count"] += 1

    # Only compare complete hours containing exactly two half-hour readings.
    actual_by_timestamp = {
        hour: {
            "timestamp": hour,
            "actual_mw": bucket["total"] / bucket["count"],
        }
        for hour, bucket in hourly_actuals.items()
        if bucket["count"] == 2
    }

    records = []

    common_timestamps = (
        selected_forecasts.keys() & actual_by_timestamp.keys()
    )

    for timestamp in sorted(common_timestamps):
        forecast = selected_forecasts[timestamp]
        actual = actual_by_timestamp[timestamp]

        error = forecast["forecast_mw"] - actual["actual_mw"]

        records.append(
            {
                "timestamp": timestamp.isoformat().replace(
                    "+00:00", "Z"
                ),
                "date": timestamp.date().isoformat(),
                "time": timestamp.strftime("%H:%M"),
                "forecast_mw": round(
                    forecast["forecast_mw"], 3
                ),
                "actual_mw": round(
                    actual["actual_mw"], 3
                ),
                "error_mw": round(error, 3),
                "absolute_error_mw": round(abs(error), 3),
                "forecast_published_at": (
                    forecast["published_at"]
                    .isoformat()
                    .replace("+00:00", "Z")
                ),
            }
        )

    buckets = {}

    for row in records:
        bucket = buckets.setdefault(
            row["date"],
            {
                "date": row["date"],
                "forecast_sum": 0.0,
                "actual_sum": 0.0,
                "absolute_error_sum": 0.0,
                "count": 0,
            },
        )

        bucket["forecast_sum"] += row["forecast_mw"]
        bucket["actual_sum"] += row["actual_mw"]
        bucket["absolute_error_sum"] += row["absolute_error_mw"]
        bucket["count"] += 1

    daily = []

    for bucket in buckets.values():
        count = bucket["count"]

        daily.append(
            {
                "date": bucket["date"],
                "forecast_mw_average": round(
                    bucket["forecast_sum"] / count, 3
                ),
                "actual_mw_average": round(
                    bucket["actual_sum"] / count, 3
                ),
                "mae_mw": round(
                    bucket["absolute_error_sum"] / count, 3
                ),
                "matched_intervals": count,
            }
        )

    return {
        "metrics": metrics(
            records,
            len(actual_by_timestamp),
        ),
        "records": records,
        "daily": daily,
        "methodology": {
            "forecast_selection": (
                "Latest forecast published by "
                f"{CUTOFF_HOUR:02d}:59:59 UTC "
                "on the day before delivery."
            ),
            "comparison": (
                "Hourly forecast values are matched to hourly actual "
                "wind averages derived from two half-hour readings. "
                "Incomplete hours are excluded."
            ),
            "timestamp_timezone": "UTC",
            "note": (
                "Forecast delivery timestamps are derived from "
                "settlementDate and settlementPeriod when available, "
                "otherwise from delivery/start timestamps. "
                "Missing values are not filled with zero. "
                "Confirm the forecast timestamp convention against "
                "the source dataset documentation before interpreting "
                "the accuracy metrics."
            ),
        },
        "source_counts": {
            "raw_forecast_rows": len(forecast_rows),
            "normalized_forecast_rows": len(normalized_forecasts),
            "eligible_forecast_intervals": len(selected_forecasts),
            "raw_actual_rows": len(actual_rows),
            "normalized_actual_wind_intervals": len(normalized_actuals),
            "complete_hourly_actual_intervals": len(actual_by_timestamp),
        },
    }


def filter_rows_by_date(rows, start, end):
    filtered = []

    for row in rows:
        timestamp = actual_timestamp(row)

        if (
            timestamp is not None
            and start <= timestamp.date() <= end
        ):
            filtered.append(row)

    return filtered


async def fetch(dataset, start, end):
    url = f"{BASE}/datasets/{dataset}/stream"

    start_dt = datetime.combine(
        start, time.min, tzinfo=timezone.utc
    )

    end_dt = datetime.combine(
        end + timedelta(days=1),
        time.min,
        tzinfo=timezone.utc,
    )

    if dataset == "FUELHH":
        params = {
            "settlementDateFrom": start.isoformat(),
            "settlementDateTo": end.isoformat(),
        }
    else:
        params = {
            "publishDateTimeFrom": start_dt.strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            "publishDateTimeTo": end_dt.strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
        }

    try:
        async with httpx.AsyncClient(
            timeout=60,
            follow_redirects=True,
        ) as client:
            response = await client.get(
                url,
                params=params,
                headers={"Accept": "application/json"},
            )

            response.raise_for_status()
            body = response.json()

    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                f"Elexon returned HTTP {exc.response.status_code} "
                f"for {dataset}. Check the dataset and parameters."
            ),
        ) from exc

    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not retrieve {dataset} from Elexon: {exc}",
        ) from exc

    if isinstance(body, list):
        rows = [
            row for row in body
            if isinstance(row, dict)
        ]

    elif isinstance(body, dict):
        rows = None

        for key in ("data", "items", "results", "result"):
            if isinstance(body.get(key), list):
                rows = [
                    row for row in body[key]
                    if isinstance(row, dict)
                ]
                break

        if rows is None:
            raise HTTPException(
                status_code=502,
                detail=f"Unexpected {dataset} response shape.",
            )

    else:
        raise HTTPException(
            status_code=502,
            detail=f"Unexpected {dataset} response shape.",
        )

    if dataset == "FUELHH":
        return filter_rows_by_date(rows, start, end)

    return rows


def validate(start, end):
    if start > end:
        raise HTTPException(
            status_code=400,
            detail="'from' must be on or before 'to'.",
        )

    if (end - start).days > 62:
        raise HTTPException(
            status_code=400,
            detail="Request up to 63 days at a time.",
        )


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "service": "gridbricks-wind-intelligence",
    }


@app.get("/api/analysis")
async def analysis(
    from_date: date = Query(
        date(2026, 1, 1), alias="from"
    ),
    to_date: date = Query(
        date(2026, 1, 31), alias="to"
    ),
):
    validate(from_date, to_date)

    forecast_rows, actual_rows = await asyncio.gather(
        fetch(
            "WINDFOR",
            from_date - timedelta(days=1),
            to_date,
        ),
        fetch(
            "FUELHH",
            from_date,
            to_date,
        ),
    )

    result = analyze(
        forecast_rows,
        actual_rows,
        from_date,
        to_date,
    )

    result["requested_period"] = {
        "from": from_date.isoformat(),
        "to": to_date.isoformat(),
    }

    return result


@app.get("/api/forecast")
async def forecast(
    from_date: date = Query(
        date(2026, 1, 1), alias="from"
    ),
    to_date: date = Query(
        date(2026, 1, 31), alias="to"
    ),
):
    validate(from_date, to_date)

    rows = await fetch(
        "WINDFOR",
        from_date - timedelta(days=1),
        to_date,
    )

    selected = select_forecasts(
        norm_forecasts(rows),
        from_date,
        to_date,
    )

    return [
        {
            "timestamp": timestamp.isoformat().replace(
                "+00:00", "Z"
            ),
            "forecast_mw": row["forecast_mw"],
            "published_at": row["published_at"].isoformat().replace(
                "+00:00", "Z"
            ),
        }
        for timestamp, row in sorted(selected.items())
    ]


@app.get("/api/actual")
async def actual(
    from_date: date = Query(
        date(2026, 1, 1), alias="from"
    ),
    to_date: date = Query(
        date(2026, 1, 31), alias="to"
    ),
):
    validate(from_date, to_date)

    rows = norm_actuals(
        await fetch("FUELHH", from_date, to_date)
    )

    return [
        {
            "timestamp": row["timestamp"].isoformat().replace(
                "+00:00", "Z"
            ),
            "actual_mw": row["actual_mw"],
        }
        for row in rows
        if from_date <= row["timestamp"].date() <= to_date
    ]


@app.get("/api/debug")
async def debug(
    from_date: date = Query(
        date(2026, 1, 1), alias="from"
    ),
    to_date: date = Query(
        date(2026, 1, 3), alias="to"
    ),
):
    validate(from_date, to_date)

    forecast_rows, actual_rows = await asyncio.gather(
        fetch(
            "WINDFOR",
            from_date - timedelta(days=1),
            to_date,
        ),
        fetch(
            "FUELHH",
            from_date,
            to_date,
        ),
    )

    normalized_forecasts = norm_forecasts(forecast_rows)

    eligible_forecasts = select_forecasts(
        normalized_forecasts,
        from_date,
        to_date,
    )

    normalized_actuals = norm_actuals(actual_rows)

    def forecast_preview(row):
        return {
            "timestamp": row["timestamp"].isoformat(),
            "forecast_mw": row["forecast_mw"],
            "published_at": (
                row["published_at"].isoformat()
                if row["published_at"] else None
            ),
        }

    return {
        "requested_period": {
            "from": from_date.isoformat(),
            "to": to_date.isoformat(),
        },
        "forecast": {
            "raw_row_count": len(forecast_rows),
            "first_raw_row": (
                forecast_rows[0] if forecast_rows else None
            ),
            "normalized_count": len(normalized_forecasts),
            "first_normalized_row": (
                forecast_preview(normalized_forecasts[0])
                if normalized_forecasts else None
            ),
            "eligible_count": len(eligible_forecasts),
            "first_eligible_row": (
                forecast_preview(
                    next(iter(eligible_forecasts.values()))
                )
                if eligible_forecasts else None
            ),
        },
        "actual": {
            "raw_row_count": len(actual_rows),
            "first_raw_row": (
                actual_rows[0] if actual_rows else None
            ),
            "normalized_count": len(normalized_actuals),
            "first_normalized_row": (
                {
                    "timestamp": normalized_actuals[0]["timestamp"].isoformat(),
                    "actual_mw": normalized_actuals[0]["actual_mw"],
                }
                if normalized_actuals else None
            ),
        },
        "sample_forecast_timestamps": [
            forecast_preview(row)
            for row in normalized_forecasts[:12]
        ],
    }