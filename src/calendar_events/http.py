"""Shared resilient HTTP helper: timeouts, retry/backoff, throttling, robots."""

from __future__ import annotations

import time
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import requests

#: Default per-request timeout in seconds.
DEFAULT_TIMEOUT = 15
#: How many attempts to make before giving up.
DEFAULT_RETRIES = 3
#: Base delay (seconds) for exponential backoff.
BACKOFF_BASE = 1.0
#: Multiplier applied to the backoff delay on each retry.
BACKOFF_FACTOR = 2.0
#: Minimum time (seconds) between requests to the same host.
MIN_REQUEST_INTERVAL = 2.0
#: User-Agent sent with every request so operators can identify this client.
USER_AGENT = "build-calendar-events/1.0 (+https://github.com/)"

# Last request timestamp per host, used for polite throttling.
_last_request: dict[str, float] = {}


def _sleep_backoff(attempt: int) -> None:
    """Sleep for an exponentially increasing delay based on the attempt index."""
    time.sleep(BACKOFF_BASE * (BACKOFF_FACTOR**attempt))


def _throttle(host: str) -> None:
    """Ensure at least MIN_REQUEST_INTERVAL seconds between requests to a host."""
    now = time.monotonic()
    last = _last_request.get(host)
    if last is not None:
        wait = MIN_REQUEST_INTERVAL - (now - last)
        if wait > 0:
            time.sleep(wait)
    _last_request[host] = time.monotonic()


def get(
    url: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
) -> requests.Response:
    """GET a URL with throttling, retries, and exponential backoff.

    Retries on connection errors, timeouts, HTTP 429, and 5xx responses. Raises
    the last exception (or ``raise_for_status`` error) once retries are spent.
    """
    host = urlsplit(url).netloc
    headers = {"User-Agent": USER_AGENT}
    last_exc: Exception | None = None
    last_response: requests.Response | None = None
    for attempt in range(retries):
        _throttle(host)
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
        except (requests.ConnectionError, requests.Timeout) as exc:
            last_exc = exc
            last_response = None
        else:
            if response.status_code != 429 and response.status_code < 500:
                response.raise_for_status()
                return response
            last_response = response
            last_exc = None
        if attempt < retries - 1:
            _sleep_backoff(attempt)
    if last_response is not None:
        last_response.raise_for_status()
        return last_response
    assert last_exc is not None  # loop ran at least once
    raise last_exc


def robots_allows(url: str) -> bool:
    """Return whether the site's robots.txt permits fetching ``url``.

    A missing robots.txt (404) is treated as allowed; any other fetch failure is
    treated as disallowed so we err on the side of not scraping.
    """
    parts = urlsplit(url)
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    try:
        response = get(robots_url)
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            return True
        return False
    except requests.RequestException:
        return False
    parser = RobotFileParser()
    parser.parse(response.text.splitlines())
    return parser.can_fetch(USER_AGENT, url)
