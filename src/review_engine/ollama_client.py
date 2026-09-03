from __future__ import annotations

import json
import re
from typing import Any

import requests

from review_engine.http_client import _ssl_verify


class OllamaError(RuntimeError):
    pass


def generate_json(
    *,
    host: str,
    model: str,
    prompt: str,
    timeout: float = 120.0,
) -> dict[str, Any]:
    url = host.rstrip("/") + "/api/generate"
    try:
        resp = requests.post(
            url,
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0},
            },
            timeout=timeout,
            verify=_ssl_verify(),
        )
    except requests.RequestException as exc:
        raise OllamaError(f"ollama unreachable at {url}: {exc}") from exc
    if resp.status_code >= 400:
        raise OllamaError(f"ollama {resp.status_code}: {resp.text[:300]}")
    payload = resp.json()
    raw = payload.get("response") or ""
    return _parse_json_object(raw)


def embed_text(
    *,
    host: str,
    model: str,
    text: str,
    timeout: float = 60.0,
) -> list[float]:
    """nomic-embed-text via Ollama. Tries /api/embed then /api/embeddings."""
    payload_embed = {"model": model, "input": text}
    url_embed = host.rstrip("/") + "/api/embed"
    try:
        resp = requests.post(
            url_embed,
            json=payload_embed,
            timeout=timeout,
            verify=_ssl_verify(),
        )
        if resp.status_code < 400:
            data = resp.json()
            vectors = data.get("embeddings") or data.get("embedding")
            vec = _first_vector(vectors)
            if vec:
                return vec
    except requests.RequestException as exc:
        raise OllamaError(f"ollama unreachable at {url_embed}: {exc}") from exc

    url_legacy = host.rstrip("/") + "/api/embeddings"
    try:
        resp = requests.post(
            url_legacy,
            json={"model": model, "prompt": text},
            timeout=timeout,
            verify=_ssl_verify(),
        )
    except requests.RequestException as exc:
        raise OllamaError(f"ollama unreachable at {url_legacy}: {exc}") from exc
    if resp.status_code >= 400:
        raise OllamaError(f"ollama {resp.status_code}: {resp.text[:300]}")
    data = resp.json()
    vec = _first_vector(data.get("embedding") or data.get("embeddings"))
    if not vec:
        raise OllamaError("ollama embed returned no vector")
    return vec


def _first_vector(value: Any) -> list[float]:
    if value is None:
        return []
    if isinstance(value, list) and value and isinstance(value[0], (int, float)):
        return [float(x) for x in value]
    if isinstance(value, list) and value and isinstance(value[0], list):
        return [float(x) for x in value[0]]
    return []


def ollama_available(host: str, timeout: float = 2.0) -> bool:
    url = host.rstrip("/") + "/api/tags"
    try:
        resp = requests.get(url, timeout=timeout, verify=_ssl_verify())
        return resp.status_code == 200
    except requests.RequestException:
        return False


def _parse_json_object(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    try:
        value = json.loads(text)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise OllamaError("model did not return JSON")
    value = json.loads(match.group(0))
    if not isinstance(value, dict):
        raise OllamaError("JSON was not an object")
    return value


generate_json = generate_json
ollama_available = ollama_available
