"""Helpers shared by the ingestion clients."""

import logging
import time
from collections.abc import Iterator
from contextlib import AbstractContextManager, nullcontext
from datetime import date, timedelta

import httpx

log = logging.getLogger(__name__)

TIMEOUT_SECONDS = 60
MAX_RETRIES = 6
RETRY_STATUSES = {429, 500, 502, 503, 504}
PAUSE_SECONDS = 1.0  # politeness delay before every request, free APIs rate-limit bursts

sleep = time.sleep  # module-level so tests can replace it and run instantly


def get_json(client: httpx.Client, url: str, params: dict) -> dict | list:
    """GET with a pause before each request and exponential backoff on failures.

    Retries 429 / 5xx responses and dropped connections. Honours the server's Retry-After
    header when present, otherwise waits 2, 4, 8, ... s.
    """
    for attempt in range(MAX_RETRIES + 1):
        last_attempt = attempt == MAX_RETRIES
        sleep(PAUSE_SECONDS)
        try:
            response = client.get(url, params=params)
        except httpx.TransportError as exc:  # connection reset, timeout, server hung up
            if last_attempt:
                raise
            wait = 2.0 ** (attempt + 1)
            log.warning("%s from %s, retrying in %.0fs", type(exc).__name__, url, wait)
            sleep(wait)
            continue
        if response.status_code not in RETRY_STATUSES or last_attempt:
            response.raise_for_status()
            return response.json()
        retry_after = response.headers.get("Retry-After", "")
        wait = float(retry_after) if retry_after.isdigit() else 2.0 ** (attempt + 1)
        log.warning("HTTP %s from %s, retrying in %.0fs", response.status_code, url, wait)
        sleep(wait)
    raise AssertionError("unreachable")


def date_chunks(start: date, end: date, days: int) -> Iterator[tuple[date, date]]:
    """Split the inclusive range [start, end] into consecutive chunks of at most `days` days.

    APIs reject or time out on very long ranges, so every client fetches in chunks.
    """
    if end < start:
        raise ValueError(f"end ({end}) is before start ({start})")
    chunk_start = start
    while chunk_start <= end:
        chunk_end = min(chunk_start + timedelta(days=days - 1), end)
        yield chunk_start, chunk_end
        chunk_start = chunk_end + timedelta(days=1)


def http_client(client: httpx.Client | None) -> AbstractContextManager[httpx.Client]:
    """Use the caller's client as-is (tests inject one), or open and close a fresh one."""
    if client is not None:
        return nullcontext(client)
    return httpx.Client(timeout=TIMEOUT_SECONDS)
