"""Helpers shared by the ingestion clients."""

from collections.abc import Iterator
from contextlib import AbstractContextManager, nullcontext
from datetime import date, timedelta

import httpx

TIMEOUT_SECONDS = 60


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
