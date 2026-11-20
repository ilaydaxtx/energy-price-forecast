import pytest

from energy_forecast.ingestion import _common


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    """Record waits instead of sleeping, so tests run instantly and can assert on backoff."""
    waits: list[float] = []
    monkeypatch.setattr(_common, "sleep", waits.append)
    return waits
