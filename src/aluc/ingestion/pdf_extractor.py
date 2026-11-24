"""Extrator e isolador da seção de referências para arquivos PDF (RF01, RF02, RNF02)."""

from __future__ import annotations

import io
import re
import unicodedata
from pathlib import Path
from typing import Callable, Union
from pypdf import PdfReader

from .pdf_ocr import recognize_pdf, recognize_pdf_bytes

_HEADINGS = {
    "references", "reference list", "references cited", "references and notes",
    "notes and references", "bibliography", "selected bibliography", "works cited",
    "literature cited", "referencias bibliograficas", "referencias", "bibliografia",
    "literatura citada",
}
_SECTION_NUMBER = re.compile(r"^(?:\d+(?:\.\d+)*|[ivxlcdm]+)(?:[.):–—-]\s*|\s+)", re.I)
_ENTRY_NUMBER = re.compile(r"^\s*(?:\[(\d+)\]|(\d+)[.)]\s+)\s*(.+)")
_YEAR = re.compile(r"\b(?:18|19|20)\d{2}\b")
_AUTHOR_START = re.compile(r"^(?:[^\W\d_]+(?:[-’'][^\W\d_]+)*,\s*\w|[A-Z]\.\s*[^\W\d_]+)", re.UNICODE)
_IDENTIFIER = re.compile(r"\b(?:doi\s*:|10\.\d{4,9}/|https?://)", re.I)
_END_HEADING = re.compile(
    r"^(?:appendix|appendices|apendices?|anexos?|supplementary (?:material|information))"
    r"(?:$|\s+[a-z0-9](?:\s|$)|\s*[:–—-]|\s+[a-z0-9]\s*[:.–—-])"
    r"|^(?:about the authors|author biographies|biographical notes|introduction|introducao)$",
    re.I,
)


def _heading_key(line: str) -> str:
    normalized = unicodedata.normalize("NFKD", line).casefold()
    normalized = "".join(
        char for char in normalized if not unicodedata.combining(char) and char not in "\u200b\u00ad"
    )
    normalized = " ".join(normalized.split())
    return _SECTION_NUMBER.sub("", normalized).strip(" :.–—-")


def _is_reference_heading(line: str) -> bool:
    key = _heading_key(line)
    return key in _HEADINGS or (
        key.replace(" ", "") in _COMPACT_HEADINGS
        and all(len(part) == 1 for part in key.split())
    )


_COMPACT_HEADINGS = {heading.replace(" ", "") for heading in _HEADINGS}
_INLINE_ENTRY = re.compile(r"\s*(?=\[\d+\]|\d+[.)]\s)")


def _numbered_bibliography(lines: list[str]) -> str:
    """Sem cabeçalho, aceita apenas listas que exibem sinais bibliográficos."""
    runs: list[list[str]] = []
    run: list[str] = []
    previous = 0
    for line in lines:
        if not line.strip():
            continue
        entry = _ENTRY_NUMBER.match(line)
        if entry and (
            _IDENTIFIER.search(entry[3])
            or (_AUTHOR_START.match(entry[3]) and _YEAR.search(entry[3]))
        ):
            number = int(entry[1] or entry[2])
            if run and number != previous + 1:
                runs.append(run)
                run = []
            run.append(line.strip())
            previous = number
        elif run:
            runs.append(run)
            run = []
    runs.append(run)
    for run in reversed(runs):
        if len(run) >= 3:
            return "\n".join(run)
    return ""


def isolate_references_from_text(full_text: str) -> str:
    """Localiza a seção ou uma lista numerada com evidências bibliográficas."""
    lines = full_text.splitlines()
    for index in range(len(lines) - 1, -1, -1):
        line = lines[index].strip()
        if not line:
            continue
        first_entry = ""
        consumed = 1
        if not _is_reference_heading(line):
            inline = next(
                (match for match in _INLINE_ENTRY.finditer(line)
                 if match.start() and _is_reference_heading(line[:match.start()])),
                None,
            )
            if inline:
                first_entry = line[inline.end():]
            elif index + 1 < len(lines) and _is_reference_heading(f"{line} {lines[index + 1]}"):
                consumed = 2
            else:
                continue

        entries = [first_entry] if first_entry else []
        for entry in lines[index + consumed:]:
            if _END_HEADING.match(_heading_key(entry)):
                break
            entries.append(entry)
        block = "\n".join(entries).strip()
        if block:
            return block

    return _numbered_bibliography(lines)


_OCR_ENTRY_NUMBER = re.compile(r"^\s*\[\s*([0-9Il|O]+)\s*([]J)])?\s+(?=\S)")
_OCR_MISREAD_BRACKETS = re.compile(r"^\s*1([0-9Il|O]{1,4}?)([]J)1])\s+(?=\S)")
_OCR_DIGITS = str.maketrans({"I": "1", "l": "1", "|": "1", "O": "0"})
_OCR_VIEWER_NOISE = re.compile(r"(?:Viewer|\d+\s*/\s*\d+|\d+/\d+/\d{4},?\s+\d+:\d+)", re.I)


def _clean_ocr_pages(pages: list[str]) -> str:
    lines = []
    for page in pages:
        page_lines = page.rstrip().splitlines()
        viewer = any(line.strip() == "Viewer" for line in page_lines)
        for index, line in enumerate(page_lines):
            if (viewer or index == len(page_lines) - 1) and _OCR_VIEWER_NOISE.fullmatch(line.strip()):
                continue
            lines.append(line)
    return "\n".join(lines)


def _normalize_ocr_entry_numbers(section: str) -> str:
    previous = 0
    lines = []
    for line in section.splitlines():
        match = _OCR_ENTRY_NUMBER.match(line) or _OCR_MISREAD_BRACKETS.match(line)
        if match:
            digits = match[1].translate(_OCR_DIGITS)
            if not match[2] and digits.endswith("1") and len(digits) > 1:
                digits = digits[:-1]
            number = int(digits)
            if (line.lstrip().startswith("[") and match[2]) or previous < number <= previous + 3:
                line = f"[{number}] {line[match.end():]}"
                previous = number
        lines.append(line)
    return "\n".join(lines)


def extract_references_section_from_pdf(
    pdf_source: Union[str, Path, bytes, io.BytesIO],
    notify: Callable[[str], None] | None = None,
) -> str:
    """Lê um arquivo PDF e retorna exclusivamente a seção de referências isolada (RF02, RNF02)."""
    if isinstance(pdf_source, (str, Path)):
        reader = PdfReader(str(pdf_source))
    elif isinstance(pdf_source, bytes):
        reader = PdfReader(io.BytesIO(pdf_source))
    else:
        reader = PdfReader(pdf_source)

    pages_text: list[str] = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        pages_text.append(page_text)

    combined_text = "\n".join(pages_text)
    section = isolate_references_from_text(combined_text)
    if section:
        return section

    if any(text.strip() for text in pages_text):
        # A ordem visual pode recuperar cabeçalhos que o fluxo do PDF intercala.
        layout_text = "\n".join(
            page.extract_text(extraction_mode="layout") or "" for page in reader.pages
        )
        section = isolate_references_from_text(layout_text)
        if section or all(text.strip() for text in pages_text):
            return section

    if notify:
        notify("Tentando reconhecer o texto das páginas com OCR local…")
    if isinstance(pdf_source, (str, Path)):
        recognized_pages = recognize_pdf(Path(pdf_source))
    else:
        data = pdf_source if isinstance(pdf_source, bytes) else pdf_source.getvalue()
        recognized_pages = recognize_pdf_bytes(data)
    section = isolate_references_from_text(_clean_ocr_pages(recognized_pages))
    return _normalize_ocr_entry_numbers(section)
