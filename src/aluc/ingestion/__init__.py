"""Camada de ingestão e isolamento da seção de referências (RF01, RF02, RNF02)."""

from pathlib import Path
from typing import Tuple

from .bib_extractor import extract_references_from_bib
from .pdf_extractor import extract_references_section_from_pdf
from .tex_extractor import extract_references_section_from_tex


def extract_references_from_file(file_path: str | Path) -> Tuple[str, str]:
    """Recebe um caminho de arquivo (.pdf, .bib, .tex) e retorna (formato, bloco_referencias_isolado).

    Garante RNF02 (Privacidade do Manuscrito): o corpo do artigo (introdução, metodologia,
    resultados) é descartado localmente antes de qualquer chamada ao LLM.
    """
    path = Path(file_path)
    ext = path.suffix.lower()

    if ext == ".pdf":
        return "PDF", extract_references_section_from_pdf(path)
    if ext == ".bib":
        return "BIB", extract_references_from_bib(path)
    if ext == ".tex":
        return "TEX", extract_references_section_from_tex(path)

    raise ValueError(
        f"Formato de arquivo não suportado: '{ext}'. Formatos aceitos (RF01): .pdf, .bib, .tex"
    )


__all__ = [
    "extract_references_from_file",
    "extract_references_section_from_pdf",
    "extract_references_from_bib",
    "extract_references_section_from_tex",
]
