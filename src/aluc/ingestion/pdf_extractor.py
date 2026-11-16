"""Extrator e isolador da seção de referências para arquivos PDF (RF01, RF02, RNF02)."""

from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Union
from pypdf import PdfReader

# Padrões de cabeçalho de seção de referências em Português, Inglês e Espanhol (RF02)
REFERENCE_HEADER_PATTERN = re.compile(
    r"(?im)^\s*(?:(?:\d+(?:\.\d+)*|[IVXLC]+)\.?\s*[-–—]?\s*)?"
    r"(?:references|referências\s+bibliográficas|referencias\s+bibliograficas|"
    r"referências|referencias|bibliografia|bibliography|works\s+cited|"
    r"literatura\s+citada)\s*$"
)

# Padrões de início de apêndice/anexo para interromper a extração após as referências
APPENDIX_HEADER_PATTERN = re.compile(
    r"(?im)^\s*(?:(?:\d+(?:\.\d+)*|[A-Z])\.?\s*[-–—]?\s*)?"
    r"(?:appendix|appendices|apêndice|apendice|apêndices|anexo|anexos)\b.*$"
)


def isolate_references_from_text(full_text: str) -> str:
    """Localiza o último cabeçalho de referências válido no texto extraído de um PDF e retorna
    apenas o bloco de referências (RF02 / RNF02), cortando todo o corpo anterior do manuscrito.
    """
    if not full_text or not full_text.strip():
        return ""

    matches = list(REFERENCE_HEADER_PATTERN.finditer(full_text))
    if matches:
        # Utiliza a última ocorrência do cabeçalho (evita sumário / Table of Contents no início)
        last_match = matches[-1]
        ref_block = full_text[last_match.end() :].strip()
    else:
        # Fallback: busca inline caso o PDF não tenha quebra de linha limpa após o título da seção
        inline_pattern = re.compile(
            r"(?i)(?:^|\n)\s*(?:\d+\.?\s*)?(references|referências\s+bibliográficas|referências|bibliografia)\b"
        )
        inline_matches = list(inline_pattern.finditer(full_text))
        if inline_matches:
            last_match = inline_matches[-1]
            ref_block = full_text[last_match.end() :].strip()
        else:
            # Se não houver cabeçalho explícito, retorna apenas os 25% finais do documento
            # para preservar a privacidade do corpo principal (RNF02)
            cutoff = max(0, int(len(full_text) * 0.75))
            ref_block = full_text[cutoff:].strip()

    # Corta apêndices ou anexos que venham depois das referências
    appendix_match = APPENDIX_HEADER_PATTERN.search(ref_block)
    if appendix_match and appendix_match.start() > 100:
        ref_block = ref_block[: appendix_match.start()].strip()

    return ref_block


def extract_references_section_from_pdf(
    pdf_source: Union[str, Path, bytes, io.BytesIO]
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
    return isolate_references_from_text(combined_text)
