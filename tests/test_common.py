from datetime import date

import httpx
import pytest

from energy_forecast.ingestion import _common
from energy_forecast.ingestion._common import date_chunks, get_json


def scripted_client(responses: list[httpx.Response]) -> httpx.Client:
    """A client whose server answers with `responses`, one per request, in order."""
    queue = iter(responses)
    return httpx.Client(transport=httpx.MockTransport(lambda request: next(queue)))


def test_get_json_retries_429_with_exponential_backoff(no_sleep):
    client = scripted_client(
        [httpx.Response(429), httpx.Response(429), httpx.Response(200, json={"ok": True})]
    )

    assert get_json(client, "https://example.test", {}) == {"ok": True}
    # pause, backoff 2s, pause, backoff 4s, pause
    p = _common.PAUSE_SECONDS
    assert no_sleep == [p, 2.0, p, 4.0, p]


def test_get_json_honours_retry_after_header(no_sleep):
    client = scripted_client(
        [httpx.Response(429, headers={"Retry-After": "30"}), httpx.Response(200, json=[])]
    )

    get_json(client, "https://example.test", {})
    assert 30.0 in no_sleep


def test_get_json_retries_dropped_connections():
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            raise httpx.RemoteProtocolError("Server disconnected without sending a response.")
        return httpx.Response(200, json={"ok": True})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert get_json(client, "https://example.test", {}) == {"ok": True}
    assert len(calls) == 2


def test_get_json_gives_up_after_max_retries():
    client = scripted_client([httpx.Response(503)] * (_common.MAX_RETRIES + 1))

    with pytest.raises(httpx.HTTPStatusError):
        get_json(client, "https://example.test", {})


def test_get_json_does_not_retry_client_errors():
    client = scripted_client([httpx.Response(404)])  # a second request would raise StopIteration

    with pytest.raises(httpx.HTTPStatusError):
        get_json(client, "https://example.test", {})


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
