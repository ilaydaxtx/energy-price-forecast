from datetime import date

import httpx
import pytest

from energy_forecast.ingestion import open_meteo


def location_payload(value: float) -> dict:
    return {
        "hourly": {
            "time": ["2024-06-01T00:00", "2024-06-01T01:00"],
            **{var: [value, value + 1] for var in open_meteo.VARIABLES},
        }
    }


def test_fetch_weather_one_column_per_variable_and_location():
    seen = {}

    def handler(request):
        seen.update(request.url.params)
        return httpx.Response(
            200, json=[location_payload(i) for i in range(len(open_meteo.LOCATIONS))]
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    df = open_meteo.fetch_weather(date(2024, 6, 1), date(2024, 6, 1), client=client)

    assert seen["timezone"] == "UTC"
    assert seen["wind_speed_unit"] == "ms"
    assert df.shape == (2, len(open_meteo.VARIABLES) * len(open_meteo.LOCATIONS))
    # Locations come back in request order, so index 2 must be "ruhr".
    assert df["temperature_2m__ruhr"].tolist() == [2, 3]
    assert str(df.index.tz) == "UTC"


def test_fetch_weather_rejects_wrong_location_count():
    def handler(request):
        return httpx.Response(200, json=[location_payload(0)])

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(ValueError, match="locations"):
        open_meteo.fetch_weather(date(2024, 6, 1), date(2024, 6, 1), client=client)
