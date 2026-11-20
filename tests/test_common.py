from datetime import date

import pytest

from energy_forecast.ingestion._common import date_chunks


def test_chunks_cover_range_without_gaps_or_overlap():
    chunks = list(date_chunks(date(2024, 1, 1), date(2024, 3, 15), days=31))
    assert chunks == [
        (date(2024, 1, 1), date(2024, 1, 31)),
        (date(2024, 2, 1), date(2024, 3, 2)),
        (date(2024, 3, 3), date(2024, 3, 15)),
    ]


def test_single_day_range():
    assert list(date_chunks(date(2024, 1, 1), date(2024, 1, 1), days=31)) == [
        (date(2024, 1, 1), date(2024, 1, 1))
    ]


def test_reversed_range_raises():
    with pytest.raises(ValueError):
        list(date_chunks(date(2024, 2, 1), date(2024, 1, 1), days=31))
