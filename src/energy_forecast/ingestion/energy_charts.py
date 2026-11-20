"""Client for the Energy-Charts API (Fraunhofer ISE), which republishes SMARD data.

Docs: https://api.energy-charts.info
License of the price data: CC BY 4.0, Bundesnetzagentur | SMARD.de

The API takes local (Europe/Berlin) calendar dates and returns UTC unix timestamps.
Day-ahead prices are hourly until 2025-09-30 and quarter-hourly from 2025-10-01,
when the European day-ahead market moved to 15-minute products.
"""

from datetime import date

import httpx
import pandas as pd

from energy_forecast.ingestion._common import date_chunks, http_client

BASE_URL = "https://api.energy-charts.info"
BIDDING_ZONE = "DE-LU"
CHUNK_DAYS = 31

# Energy-Charts production type name -> our column name (values in MW)
POWER_COLUMNS = {
    "Load": "load_mw",
    "Residual load": "residual_load_mw",
    "Solar": "solar_mw",
    "Wind onshore": "wind_onshore_mw",
    "Wind offshore": "wind_offshore_mw",
}


def _get(client: httpx.Client, path: str, params: dict) -> dict:
    response = client.get(f"{BASE_URL}/{path}", params=params)
    response.raise_for_status()
    return response.json()


def _to_utc_index(unix_seconds: list[int]) -> pd.DatetimeIndex:
    return pd.to_datetime(unix_seconds, unit="s", utc=True).rename("timestamp")


def _combine(frames: list[pd.DataFrame]) -> pd.DataFrame:
    df = pd.concat(frames)
    return df[~df.index.duplicated(keep="last")].sort_index()


def fetch_prices(start: date, end: date, client: httpx.Client | None = None) -> pd.DataFrame:
    """Day-ahead prices for DE-LU in EUR/MWh, indexed by UTC timestamp (native resolution)."""
    with http_client(client) as c:
        frames = []
        for chunk_start, chunk_end in date_chunks(start, end, CHUNK_DAYS):
            payload = _get(
                c,
                "price",
                {
                    "bzn": BIDDING_ZONE,
                    "start": chunk_start.isoformat(),
                    "end": chunk_end.isoformat(),
                },
            )
            frames.append(
                pd.DataFrame(
                    {"price_eur_mwh": payload["price"]},
                    index=_to_utc_index(payload["unix_seconds"]),
                )
            )
    return _combine(frames)


def fetch_power(start: date, end: date, client: httpx.Client | None = None) -> pd.DataFrame:
    """Load and renewable generation for Germany in MW, indexed by UTC timestamp (15 min)."""
    with http_client(client) as c:
        frames = []
        for chunk_start, chunk_end in date_chunks(start, end, CHUNK_DAYS):
            payload = _get(
                c,
                "public_power",
                {"country": "de", "start": chunk_start.isoformat(), "end": chunk_end.isoformat()},
            )
            series = {
                POWER_COLUMNS[p["name"]]: p["data"]
                for p in payload["production_types"]
                if p["name"] in POWER_COLUMNS
            }
            missing = set(POWER_COLUMNS.values()) - series.keys()
            if missing:
                raise ValueError(f"Energy-Charts response is missing {sorted(missing)}")
            frames.append(pd.DataFrame(series, index=_to_utc_index(payload["unix_seconds"])))
    return _combine(frames)[list(POWER_COLUMNS.values())]


def to_hourly(df: pd.DataFrame) -> pd.DataFrame:
    """Average sub-hourly values into hourly buckets (hourly input passes through unchanged)."""
    return df.resample("1h").mean()
