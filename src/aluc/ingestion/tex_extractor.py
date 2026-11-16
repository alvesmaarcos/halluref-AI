"""Extrator e isolador da seção de referências para arquivos LaTeX (.tex) (RF01, RF02, RNF02)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Union

THEBIBLIOGRAPHY_PATTERN = re.compile(
    r"\\begin\{thebibliography\}.*?\\end\{thebibliography\}",
    re.DOTALL | re.IGNORECASE,
)

FILECONTENTS_BIB_PATTERN = re.compile(
    r"\\begin\{filecontents\*?\}\{[^}]*\.bib\}(.*?)\\end\{filecontents\*?\}",
    re.DOTALL | re.IGNORECASE,
)

BIBITEM_SPLIT_PATTERN = re.compile(
    r"(?=\\bibitem(?:\[[^\]]*\])?\{[^}]+\})",
    re.IGNORECASE,
)


def isolate_references_from_tex(tex_content: str) -> str:
    """Isola apenas os blocos de referências de um documento .tex (RNF02).

    Procura em ordem:
    1. Ambiente \\begin{thebibliography} ... \\end{thebibliography}
    2. Ambiente filecontents contendo entradas .bib embutidas
    3. Comandos \\bibitem soltos no final do documento
    4. Seção \\section*{References} / \\section*{Referências}
    """
    if not tex_content or not tex_content.strip():
        return ""

    # 1. Ambiente thebibliography
    bib_envs = THEBIBLIOGRAPHY_PATTERN.findall(tex_content)
    if bib_envs:
        return "\n\n".join(bib_envs).strip()

    # 2. Blocos filecontents .bib embutidos no .tex
    embedded_bibs = FILECONTENTS_BIB_PATTERN.findall(tex_content)
    if embedded_bibs:
        return "\n\n".join(b.strip() for b in embedded_bibs).strip()

    # 3. Comandos \bibitem
    first_bibitem = re.search(r"\\bibitem(?:\[[^\]]*\])?\{", tex_content)
    if first_bibitem:
        end_doc = re.search(r"\\end\{document\}", tex_content[first_bibitem.start() :])
        if end_doc:
            return tex_content[
                first_bibitem.start() : first_bibitem.start() + end_doc.start()
            ].strip()
        return tex_content[first_bibitem.start() :].strip()

    # 4. Seção explícita de Referências/Bibliografia no final do .tex
    sec_pattern = re.compile(
        r"\\(?:section|chapter)\*?\{(?:References|Referências|Referências Bibliográficas|Bibliografia)\}",
        re.IGNORECASE,
    )
    sec_matches = list(sec_pattern.finditer(tex_content))
    if sec_matches:
        start_idx = sec_matches[-1].end()
        end_doc = re.search(r"\\end\{document\}", tex_content[start_idx:])
        if end_doc:
            return tex_content[start_idx : start_idx + end_doc.start()].strip()
        return tex_content[start_idx:].strip()

    return ""


def extract_references_section_from_tex(tex_source: Union[str, Path]) -> str:
    """Lê um arquivo .tex (ou string LaTeX) e retorna somente a seção de referências isolada."""
    if isinstance(tex_source, Path) or (
        isinstance(tex_source, str)
        and "\n" not in tex_source
        and Path(tex_source).exists()
    ):
        raw_tex = Path(tex_source).read_text(encoding="utf-8", errors="replace")
    else:
        raw_tex = str(tex_source)

    return isolate_references_from_tex(raw_tex)
