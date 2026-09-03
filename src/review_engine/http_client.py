from __future__ import annotations

import os
import time
from typing import Any

import requests

DEFAULT_HEADERS = {
    "User-Agent": "MyntraReviewDiscoveryEngine/0.1 (local research; polite collector)",
    "Accept": "application/json",
}


def _ssl_verify() -> bool | str:
    bundle = os.getenv("SSL_CERT_FILE") or os.getenv("REQUESTS_CA_BUNDLE")
    if bundle:
        return bundle
    flag = os.getenv("REVIEW_ENGINE_SSL_VERIFY", "true").lower()
    return flag not in {"0", "false", "no"}


class HttpError(RuntimeError):
    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


def request_json(
    method: str,
    url: str,
    *,
    session: requests.Session | None = None,
    timeout: float = 30.0,
    retries: int = 3,
    headers: dict[str, str] | None = None,
    **kwargs: Any,
) -> Any:
    sess = session or requests.Session()
    merged = {**DEFAULT_HEADERS, **(headers or {})}
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            resp = sess.request(method, url, timeout=timeout, headers=merged, verify=_ssl_verify(), **kwargs)
            if resp.status_code == 429 or resp.status_code >= 500:
                retry_after = resp.headers.get("Retry-After")
                wait = float(retry_after) if retry_after and retry_after.isdigit() else 2 ** attempt
                time.sleep(wait)
                last_exc = HttpError(f"{resp.status_code} for {url}", resp.status_code)
                continue
            if resp.status_code >= 400:
                raise HttpError(f"{resp.status_code} for {url}: {resp.text[:200]}", resp.status_code)
            if not resp.content:
                return None
            return resp.json()
        except (requests.RequestException, ValueError) as exc:
            last_exc = exc
            time.sleep(2 ** attempt)
    raise HttpError(f"failed {method} {url}: {last_exc}") from last_exc
