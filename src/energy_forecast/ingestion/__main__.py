"""Download all raw sources for a date range into Parquet files.

Usage:
    uv run python -m energy_forecast.ingestion --start 2023-01-01 --end 2023-01-31
"""

import argparse
import logging
from datetime import date
from pathlib import Path

from energy_forecast.ingestion import energy_charts, open_meteo

log = logging.getLogger(__name__)

SOURCES = {
    "prices": energy_charts.fetch_prices,
    "power": energy_charts.fetch_power,
    "weather": open_meteo.fetch_weather,
}


def run(start: date, end: date, out_dir: Path) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = {}
    for name, fetch in SOURCES.items():
        log.info("fetching %s %s..%s", name, start, end)
        df = fetch(start, end)
        path = out_dir / f"{name}.parquet"
        df.to_parquet(path)
        log.info("wrote %d rows to %s", len(df), path)
        written[name] = path
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument("--out", type=Path, default=Path("data/raw"))
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run(args.start, args.end, args.out)


if __name__ == "__main__":
    main()
