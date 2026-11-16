"""Conector para a API pública do Semantic Scholar (Seção 1 / Fallback 3)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from aluc.clients.http_client import PoliteHttpClient
from aluc.schemas import OfficialWorkMetadata


def _extract_s2_paper_metadata(item: Dict[str, Any]) -> OfficialWorkMetadata:
    """Converte um registro de artigo do Semantic Scholar para OfficialWorkMetadata."""
    title = (item.get("title") or "").strip()
    authors = [
        (a.get("name") or "").strip()
        for a in (item.get("authors") or [])
        if (a.get("name") or "").strip()
    ]
    year = item.get("year")
    if not isinstance(year, int):
        year = None

    venue = (item.get("venue") or "").strip() or None
    ext_ids = item.get("externalIds") or {}
    doi = ext_ids.get("DOI") or None
    url = item.get("url") or (f"https://doi.org/{doi}" if doi else None)

    return OfficialWorkMetadata(
        fonte_api="Semantic Scholar",
        titulo_oficial=title,
        autores_oficiais=authors,
        ano_oficial=year,
        veiculo_oficial=venue,
        doi_oficial=doi,
        url_oficial=url,
        tipo_oficial="article",
    )


class SemanticScholarClient:
    """Cliente para busca bibliográfica no Semantic Scholar Graph API v1."""

    SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"

    def __init__(self, http_client: PoliteHttpClient) -> None:
        self.http = http_client

    def search_by_title(
        self, title: str, limit: int = 5
    ) -> List[OfficialWorkMetadata]:
        """Busca artigos no Semantic Scholar pelo título."""
        if not title or not title.strip():
            return []

        params = {
            "query": title.strip(),
            "limit": limit,
            "fields": "title,authors,year,venue,externalIds,url",
        }
        status, data = self.http.get_json(self.SEARCH_URL, params=params)
        if status != 200 or not data:
            return []

        items = data.get("data") or []
        return [_extract_s2_paper_metadata(item) for item in items]
