from datetime import date

import httpx
import pandas as pd
import pytest

from energy_forecast.ingestion import energy_charts

# 2025-09-30 22:00 UTC = 2025-10-01 00:00 Berlin, the first quarter-hourly delivery period.
SWITCH = 1759269600


def mock_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_fetch_prices_builds_utc_index_and_sends_zone():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.url.params)
        return httpx.Response(
            200,
            json={
                "unix_seconds": [SWITCH - 3600, SWITCH],
                "price": [80.5, 90.0],
                "unit": "EUR / MWh",
            },
        )

    df = energy_charts.fetch_prices(
        date(2025, 9, 30), date(2025, 9, 30), client=mock_client(handler)
    )

    assert seen["bzn"] == "DE-LU"
    assert list(df["price_eur_mwh"]) == [80.5, 90.0]
    assert str(df.index.tz) == "UTC"
    assert df.index[1] == pd.Timestamp("2025-09-30 22:00", tz="UTC")


def test_fetch_prices_deduplicates_across_chunks():
    # Every chunk returns the same timestamp; the result must contain it once.
    def handler(request):
        return httpx.Response(200, json={"unix_seconds": [SWITCH], "price": [1.0]})

    calls = []

    def counting_handler(request):
        calls.append(request)
        return handler(request)

    # Two years spans more than one PRICE_CHUNK_DAYS chunk.
    df = energy_charts.fetch_prices(
        date(2024, 1, 1), date(2025, 12, 31), client=mock_client(counting_handler)
    )
    assert len(calls) > 1
    assert len(df) == 1


def test_fetch_power_selects_and_renames_columns():
    def handler(request):
        types = [
            {"name": name, "data": [i, i + 1]} for i, name in enumerate(energy_charts.POWER_COLUMNS)
        ]
        types.append({"name": "Fossil gas", "data": [99, 99]})
        return httpx.Response(
            200, json={"unix_seconds": [SWITCH, SWITCH + 900], "production_types": types}
        )

    df = energy_charts.fetch_power(
        date(2025, 10, 1), date(2025, 10, 1), client=mock_client(handler)
    )

    assert list(df.columns) == list(energy_charts.POWER_COLUMNS.values())
    assert "Fossil gas" not in df.columns
    assert df["load_mw"].tolist() == [0, 1]


def test_fetch_power_fails_loudly_when_a_series_is_missing():
    def handler(request):
        return httpx.Response(
            200,
            json={"unix_seconds": [SWITCH], "production_types": [{"name": "Solar", "data": [1]}]},
        )

    with pytest.raises(ValueError, match="missing"):
        energy_charts.fetch_power(date(2025, 10, 1), date(2025, 10, 1), client=mock_client(handler))


def test_to_hourly_averages_quarter_hours():
    index = pd.date_range("2025-10-01 00:00", periods=8, freq="15min", tz="UTC")
    df = pd.DataFrame({"price_eur_mwh": [10, 20, 30, 40, 0, 0, 0, 100]}, index=index)

    hourly = energy_charts.to_hourly(df)

    assert hourly["price_eur_mwh"].tolist() == [25.0, 25.0]
