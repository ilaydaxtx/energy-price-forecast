# German Day-Ahead Electricity Price Forecast

Forecasting hourly day-ahead electricity prices for the German-Luxembourg bidding zone (DE-LU)
from public market, grid and weather-forecast data.

> **Status:** work in progress. Week 1: data ingestion.

## The problem

Every day at 12:00 CET, the day-ahead auction sets electricity prices for each period of the
next day. A forecast is only useful if it is made **before** that auction closes, using only
information available at that time. This project treats that constraint seriously:

- Weather inputs are **archived forecasts**, not observed weather. Observed weather would leak
  information that no model has in production.
- Validation uses time-ordered backtesting, never random train/test splits.

## Data sources

| Data | Source | Resolution | License |
|---|---|---|---|
| Day-ahead prices (DE-LU) | [Energy-Charts API](https://api.energy-charts.info) (data: Bundesnetzagentur / SMARD.de) | hourly, 15 min from 2025-10-01 | CC BY 4.0 |
| Load, solar, wind generation | Energy-Charts API | 15 min | see source |
| Weather forecasts (5 German regions) | [Open-Meteo Historical Forecast API](https://open-meteo.com/en/docs/historical-forecast-api) | hourly | CC BY 4.0 |

Note: since 1 October 2025 the European day-ahead market trades 15-minute products. The first
model version works at hourly resolution (averaging quarter-hours).

## Quickstart

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run python -m energy_forecast.ingestion --start 2024-01-01 --end 2024-01-31
uv run pytest
```

Raw data is written to `data/raw/*.parquet` (not committed).

## Project structure

```
src/energy_forecast/
  ingestion/     API clients and download CLI
tests/           unit tests (network calls are mocked)
```

## Roadmap

- [x] Data ingestion (prices, load/generation, weather forecasts)
- [ ] Exploratory data analysis
- [ ] Baselines and feature engineering
- [ ] Gradient-boosting model with time-series backtesting (MLflow)
- [ ] FastAPI service + Streamlit dashboard, Docker
- [ ] Daily automated pipeline (GitHub Actions) and public demo
