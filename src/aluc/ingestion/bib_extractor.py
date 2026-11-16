"""Extrator de referências para arquivos BibTeX (.bib) (RF01)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Union
import bibtexparser

from aluc.schemas import ParsedReference, ReferenceType


def _clean_latex_markup(value: str) -> str:
    """Remove chaves e comandos básicos de formatação LaTeX de campos BibTeX."""
    if not value:
        return ""
    cleaned = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", str(value))
    cleaned = cleaned.replace("{", "").replace("}", "").replace("\\", "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _normalize_doi(raw_doi: str | None) -> str | None:
    """Extrai apenas o identificador 10.xxxx/yyyy de um campo DOI ou URL."""
    if not raw_doi:
        return None
    match = re.search(r"(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)", str(raw_doi).strip())
    if match:
        return match.group(1).rstrip(".")
    return None


def _map_bib_entry_type(entry_type: str, fields: Dict[str, str]) -> ReferenceType:
    """Mapeia o tipo da entrada BibTeX e seus metadados para ReferenceType (RN05)."""
    et = (entry_type or "").lower().strip()
    title_upper = (fields.get("title", "") or "").upper()
    org_upper = (
        (fields.get("organization", "") or "")
        + " "
        + (fields.get("institution", "") or "")
        + " "
        + (fields.get("author", "") or "")
    ).upper()

    if any(
        kw in title_upper or kw in org_upper
        for kw in ["ABNT", "NBR ", "ISO ", "ISO/", "IEEE STD", "NORMA TÉCNICA"]
    ):
        return ReferenceType.STANDARD
    if any(
        kw in title_upper or kw in org_upper
        for kw in ["LEI Nº", "LEI N.", "DECRETO Nº", "PORTARIA Nº", "CONSTITUIÇÃO"]
    ):
        return ReferenceType.LEGISLATION

    if et in {"article"}:
        return ReferenceType.ARTICLE
    if et in {"inproceedings", "conference", "proceedings"}:
        return ReferenceType.CONFERENCE
    if et in {"book", "inbook", "incollection"}:
        return ReferenceType.BOOK
    if et in {"phdthesis", "mastersthesis", "thesis", "monography"}:
        return ReferenceType.THESIS
    if et in {"techreport", "manual"}:
        return ReferenceType.TECHREPORT
    if et in {"misc", "online", "electronic", "webpage"}:
        if fields.get("url") or fields.get("howpublished"):
            return ReferenceType.WEBPAGE
        return ReferenceType.OTHER
    return ReferenceType.ARTICLE


def extract_references_from_bib(bib_source: Union[str, Path]) -> str:
    """Lê o conteúdo de um arquivo .bib (ou texto BibTeX) e retorna as entradas limpas."""
    if isinstance(bib_source, Path) or (
        isinstance(bib_source, str)
        and "\n" not in bib_source
        and Path(bib_source).exists()
    ):
        raw_content = Path(bib_source).read_text(encoding="utf-8", errors="replace")
    else:
        raw_content = str(bib_source)

    return raw_content.strip()


def parse_bibtex_entries_deterministic(bib_text: str) -> List[ParsedReference]:
    """Converte entradas BibTeX diretamente em objetos ParsedReference compatível com bibtexparser v2 e v1."""
    parsed_list: List[ParsedReference] = []

    if hasattr(bibtexparser, "parse_string"):
        # API bibtexparser v2.x
        library = bibtexparser.parse_string(bib_text)
        entries_normalized: list[tuple[str, str, Dict[str, str]]] = []
        for entry in library.entries:
            fields_map = {
                k.lower(): str(field.value)
                for k, field in entry.fields_dict.items()
            }
            entries_normalized.append(
                (entry.entry_type, entry.raw or str(fields_map), fields_map)
            )
    else:
        # Fallback bibtexparser v1.x
        bib_db = bibtexparser.loads(bib_text)
        entries_normalized = [
            (
                str(e.get("ENTRYTYPE", "article")),
                str(e),
                {k.lower(): str(v) for k, v in e.items()},
            )
            for e in bib_db.entries
        ]

    for entry_type, raw_original, fields in entries_normalized:
        title = _clean_latex_markup(fields.get("title", ""))
        raw_authors = _clean_latex_markup(fields.get("author", ""))
        if raw_authors:
            authors = [
                a.strip()
                for a in re.split(r"\s+and\s+", raw_authors, flags=re.IGNORECASE)
                if a.strip()
            ]
        else:
            authors = []

        year_val: int | None = None
        raw_year = fields.get("year", "")
        if raw_year:
            ym = re.search(r"\b(1[89]\d{2}|20\d{2})\b", str(raw_year))
            if ym:
                year_val = int(ym.group(1))

        venue = (
            _clean_latex_markup(
                fields.get("journal")
                or fields.get("booktitle")
                or fields.get("publisher")
                or fields.get("institution")
                or fields.get("howpublished")
                or ""
            )
            or None
        )

        doi = _normalize_doi(fields.get("doi") or fields.get("url"))
        url = fields.get("url") or None
        if not url and fields.get("howpublished"):
            url_match = re.search(r"(https?://[^\s}]+)", fields.get("howpublished", ""))
            if url_match:
                url = url_match.group(1)

        ref_type = _map_bib_entry_type(entry_type, fields)

        parsed_list.append(
            ParsedReference(
                texto_original=raw_original.strip(),
                titulo=title,
                autores=authors,
                ano=year_val,
                veiculo=venue,
                doi=doi,
                url=url,
                tipo_inferido=ref_type,
            )
        )

    return parsed_list
