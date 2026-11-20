"""Client for Open-Meteo's Historical Forecast API.

Docs: https://open-meteo.com/en/docs/historical-forecast-api
License: CC BY 4.0, free for non-commercial use.

Why forecasts and not observed weather: on day D-1 at 12:00 (auction close) nobody knows
tomorrow's actual weather, only a forecast. Training on observed weather would leak
information the model can never have in production. This API archives past model runs.

Known limitation: the archive is stitched from the first hours of each forecast run, so its
lead time is shorter (and its error smaller) than a real D-1 forecast for the next day.
"""

from datetime import date

import httpx
import pandas as pd

from energy_forecast.ingestion._common import date_chunks, http_client

BASE_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"
CHUNK_DAYS = 92

VARIABLES = ["temperature_2m", "wind_speed_100m", "shortwave_radiation", "cloud_cover"]

# A few points that stand in for the regions that drive German supply and demand.
LOCATIONS = {
    "north_sea": (54.48, 9.05),  # Schleswig-Holstein coast: onshore wind
    "baltic": (53.85, 12.20),  # Mecklenburg-Vorpommern: onshore wind
    "ruhr": (51.51, 7.47),  # Dortmund: industrial and urban load
    "central": (51.30, 9.50),  # Hesse: mixed
    "south": (48.40, 11.00),  # Bavaria: solar
}


def fetch_weather(start: date, end: date, client: httpx.Client | None = None) -> pd.DataFrame:
    """Hourly weather forecasts, one column per `<variable>__<location>`, UTC index."""
    names = list(LOCATIONS)
    lats = ",".join(str(LOCATIONS[n][0]) for n in names)
    lons = ",".join(str(LOCATIONS[n][1]) for n in names)

    with http_client(client) as c:
        frames = []
        for chunk_start, chunk_end in date_chunks(start, end, CHUNK_DAYS):
            response = c.get(
                BASE_URL,
                params={
                    "latitude": lats,
                    "longitude": lons,
                    "start_date": chunk_start.isoformat(),
                    "end_date": chunk_end.isoformat(),
                    "hourly": ",".join(VARIABLES),
                    "wind_speed_unit": "ms",
                    "timezone": "UTC",
                },
            )
            response.raise_for_status()
            payload = response.json()
            # A multi-location request returns a list with one entry per location, in order.
            per_location = payload if isinstance(payload, list) else [payload]
            if len(per_location) != len(names):
                raise ValueError(f"expected {len(names)} locations, got {len(per_location)}")

            columns = {}
            for name, loc in zip(names, per_location, strict=True):
                for var in VARIABLES:
                    columns[f"{var}__{name}"] = loc["hourly"][var]
            index = pd.to_datetime(per_location[0]["hourly"]["time"], utc=True).rename("timestamp")
            frames.append(pd.DataFrame(columns, index=index))

    df = pd.concat(frames)
    return df[~df.index.duplicated(keep="last")].sort_index()
