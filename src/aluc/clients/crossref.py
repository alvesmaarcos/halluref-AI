"""Conector para a API pública do Crossref e resolução de DOI no doi.org (RN01, RF04, RNF04)."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

from aluc.clients.http_client import PoliteHttpClient
from aluc.schemas import OfficialWorkMetadata


def _extract_crossref_item_metadata(item: Dict[str, Any]) -> OfficialWorkMetadata:
    """Converte um registro de obra do Crossref para OfficialWorkMetadata."""
    titles = item.get("title") or []
    title = titles[0] if titles else ""
    # Remove eventuais tags HTML simples presentes em títulos do Crossref
    title = re.sub(r"<[^>]+>", "", title).strip()

    authors: List[str] = []
    for author in item.get("author") or []:
        given = (author.get("given") or "").strip()
        family = (author.get("family") or author.get("name") or "").strip()
        if given and family:
            authors.append(f"{given} {family}")
        elif family:
            authors.append(family)

    # Extração de ano (published-print, published-online ou issued)
    year: Optional[int] = None
    for date_field in ("published-print", "published-online", "issued", "created"):
        date_obj = item.get(date_field) or {}
        parts = date_obj.get("date-parts") or []
        if parts and parts[0] and isinstance(parts[0][0], int):
            year = parts[0][0]
            break

    containers = item.get("container-title") or []
    venue = containers[0] if containers else (item.get("publisher") or None)

    doi = item.get("DOI")
    url = item.get("URL") or (f"https://doi.org/{doi}" if doi else None)
    work_type = item.get("type")

    return OfficialWorkMetadata(
        fonte_api="Crossref",
        titulo_oficial=title,
        autores_oficiais=authors,
        ano_oficial=year,
        veiculo_oficial=venue,
        doi_oficial=doi,
        url_oficial=url,
        tipo_oficial=work_type,
    )


class CrossrefClient:
    """Cliente para resolução de DOI (RN01) e busca bibliográfica no Crossref (RF04)."""

    BASE_URL = "https://api.crossref.org/works"
    DOI_HANDLE_URL = "https://doi.org/api/handles"

    def __init__(self, http_client: PoliteHttpClient) -> None:
        self.http = http_client

    def resolve_doi(
        self, raw_doi: str
    ) -> Tuple[str, Optional[OfficialWorkMetadata]]:
        """Resolve um DOI diretamente no Crossref e doi.org conforme RN01.

        Retorna (status_resolucao, metadados_oficiais):
        - ('RESOLVIDO', OfficialWorkMetadata): DOI encontrado no Crossref.
        - ('INEXISTENTE_404', None): DOI retornou 404 no Crossref e no doi.org (RN01 Critério 1).
        - ('REGISTRADO_SEM_METADADOS_CROSSREF', None): DOI existe no doi.org (ex: DataCite), mas não no Crossref.
        """
        clean_doi = raw_doi.strip()
        clean_doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", clean_doi, flags=re.I)
        encoded_doi = quote(clean_doi.lower(), safe="")

        url = f"{self.BASE_URL}/{encoded_doi}"
        status, data = self.http.get_json(url)

        if status == 200 and data and "message" in data:
            return "RESOLVIDO", _extract_crossref_item_metadata(data["message"])

        # Verifica no doi.org se o handle existe em outra agência (ex: DataCite)
        handle_url = f"{self.DOI_HANDLE_URL}/{encoded_doi}"
        h_status, h_data = self.http.get_json(handle_url)
        if h_status == 404 or (h_data and h_data.get("responseCode") == 100):
            return "INEXISTENTE_404", None

        if h_status == 200 and h_data and h_data.get("responseCode") == 1:
            return "REGISTRADO_OUTRA_AGENCIA", None

        return "ERRO_CONEXAO", None

    def search_by_title(
        self,
        title: str,
        rows: int = 5,
        first_author_surname: Optional[str] = None,
    ) -> List[OfficialWorkMetadata]:
        """Busca obras no Crossref pelo título bibliográfico (RF04).

        Executa primeiro a busca somente pelo título (para detectar Referências Quimera onde o título
        existe mas pertence a outros autores) e, se `first_author_surname` for informado, complementa
        com busca combinada título + autor para desambiguar títulos curtos/homônimos.
        """
        if not title or not title.strip():
            return []

        params = {
            "query.title": title.strip(),
            "rows": rows,
        }
        status, data = self.http.get_json(self.BASE_URL, params=params)
        items = (
            ((data.get("message") or {}).get("items") or [])
            if (status == 200 and data)
            else []
        )
        results = [_extract_crossref_item_metadata(item) for item in items]

        if first_author_surname and first_author_surname.strip():
            params_author = {
                "query.title": title.strip(),
                "query.author": first_author_surname.strip(),
                "rows": rows,
            }
            status_a, data_a = self.http.get_json(self.BASE_URL, params=params_author)
            if status_a == 200 and data_a:
                items_a = (data_a.get("message") or {}).get("items") or []
                results.extend(
                    _extract_crossref_item_metadata(item) for item in items_a
                )

        return results
