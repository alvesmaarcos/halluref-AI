"""Cliente HTTP com controle de taxa (Rate Limiting) e cabeçalho Polite Pool (RNF04)."""

from __future__ import annotations

import time
from typing import Any, Dict, Optional
from urllib.parse import urlparse
import httpx

from aluc.config import AlucConfig


class PoliteHttpClient:
    """Gerencia chamadas HTTP às APIs científicas públicas respeitando Rate Limiting (RNF04)."""

    def __init__(self, config: Optional[AlucConfig] = None) -> None:
        self.config = config or AlucConfig.from_env()
        self._last_call_by_host: Dict[str, float] = {}
        self._client = httpx.Client(
            timeout=self.config.http_timeout_sec,
            headers={
                "User-Agent": self.config.user_agent,
                "Accept": "application/json",
            },
            follow_redirects=True,
        )

    def _get_min_interval(self, host: str) -> float:
        host_lower = host.lower()
        if "crossref.org" in host_lower or "doi.org" in host_lower:
            return self.config.crossref_min_interval_sec
        if "openalex.org" in host_lower:
            return self.config.openalex_min_interval_sec
        if "semanticscholar.org" in host_lower:
            return self.config.semantic_scholar_min_interval_sec
        return 0.25

    def _wait_for_rate_limit(self, url: str) -> None:
        parsed = urlparse(url)
        host = parsed.netloc or "default"
        min_interval = self._get_min_interval(host)
        now = time.monotonic()
        last_time = self._last_call_by_host.get(host, 0.0)
        elapsed = now - last_time
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_call_by_host[host] = time.monotonic()

    def get_json(
        self, url: str, params: Optional[Dict[str, Any]] = None
    ) -> tuple[int, Optional[Dict[str, Any]]]:
        """Executa GET respeitando o Rate Limiting e retorna (status_code, json_dict_ou_None)."""
        self._wait_for_rate_limit(url)
        try:
            response = self._client.get(url, params=params)
            if response.status_code == 200:
                return 200, response.json()
            return response.status_code, None
        except httpx.HTTPError:
            return 503, None

    def close(self) -> None:
        self._client.close()
