"""Conector para a API pública do OpenAlex (RF04, RNF04)."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from aluc.clients.http_client import PoliteHttpClient
from aluc.schemas import OfficialWorkMetadata


def _extract_openalex_work_metadata(item: Dict[str, Any]) -> OfficialWorkMetadata:
    """Converte um registro de obra do OpenAlex para OfficialWorkMetadata."""
    title = (item.get("display_name") or item.get("title") or "").strip()
    title = re.sub(r"<[^>]+>", "", title).strip()

    authors: List[str] = []
    for authorship in item.get("authorships") or []:
        author_obj = authorship.get("author") or {}
        name = (author_obj.get("display_name") or "").strip()
        if name:
            authors.append(name)

    year = item.get("publication_year")
    if not isinstance(year, int):
        year = None

    primary_loc = item.get("primary_location") or {}
    source_obj = primary_loc.get("source") or {}
    venue = source_obj.get("display_name") or None

    raw_doi = item.get("doi") or ""
    doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", raw_doi, flags=re.I).strip() or None
    url = primary_loc.get("landing_page_url") or raw_doi or item.get("id")
    work_type = item.get("type")

    return OfficialWorkMetadata(
        fonte_api="OpenAlex",
        titulo_oficial=title,
        autores_oficiais=authors,
        ano_oficial=year,
        veiculo_oficial=venue,
        doi_oficial=doi,
        url_oficial=url,
        tipo_oficial=work_type,
    )


class OpenAlexClient:
    """Cliente para busca bibliográfica e resolução de DOI na API do OpenAlex (RF04)."""

    BASE_URL = "https://api.openalex.org/works"

    def __init__(self, http_client: PoliteHttpClient) -> None:
        self.http = http_client

    def resolve_doi(self, raw_doi: str) -> Optional[OfficialWorkMetadata]:
        """Tenta resolver um DOI diretamente no OpenAlex (útil para DOIs DataCite/arXiv)."""
        clean_doi = raw_doi.strip()
        clean_doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", clean_doi, flags=re.I)
        doi_url = f"https://doi.org/{clean_doi}"
        url = f"{self.BASE_URL}/{quote(doi_url, safe=':/')}"
        status, data = self.http.get_json(url)
        if status == 200 and data and data.get("id"):
            return _extract_openalex_work_metadata(data)
        return None

    def search_by_title(
        self, title: str, per_page: int = 5
    ) -> List[OfficialWorkMetadata]:
        """Busca obras no OpenAlex pelo título."""
        if not title or not title.strip():
            return []

        params = {
            "search": title.strip(),
            "per-page": per_page,
        }
        status, data = self.http.get_json(self.BASE_URL, params=params)
        if status != 200 or not data:
            return []

        results = data.get("results") or []
        return [_extract_openalex_work_metadata(item) for item in results]
