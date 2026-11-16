"""Testes unitários para a camada de ingestão e isolamento de referências (RF01, RF02, RNF02)."""

import io
from fpdf import FPDF

from aluc.ingestion.bib_extractor import parse_bibtex_entries_deterministic
from aluc.ingestion.pdf_extractor import (
    extract_references_section_from_pdf,
    isolate_references_from_text,
)
from aluc.ingestion.tex_extractor import isolate_references_from_tex
from aluc.schemas import ReferenceType


def test_isolate_references_from_text_removes_manuscript_body():
    """Garante RNF02 e RF02: o corpo do artigo (introdução/metodologia) é descartado."""
    manuscript = (
        "1. Introdução\n"
        "Este artigo apresenta dados confidenciais do laboratório.\n\n"
        "2. Metodologia\n"
        "Experimentos inéditos foram conduzidos em 2026.\n\n"
        "Referências Bibliográficas\n"
        "[1] LeCun, Y., Bengio, Y., Hinton, G. (2015). Deep learning. Nature, 521, 436-444.\n"
        "[2] Vaswani, A. et al. (2017). Attention Is All You Need. NeurIPS.\n\n"
        "Apêndice A - Tabelas Auxiliares\n"
        "Dados suplementares que não fazem parte das referências."
    )
    isolated = isolate_references_from_text(manuscript)

    assert "dados confidenciais do laboratório" not in isolated
    assert "Experimentos inéditos" not in isolated
    assert "LeCun, Y." in isolated
    assert "Attention Is All You Need" in isolated
    assert "Dados suplementares" not in isolated


def test_extract_references_section_from_real_pdf_bytes():
    """Cria um PDF em memória com múltiplas seções e valida a extração isolada (RF01, RF02)."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(
        0,
        8,
        "1. Introduction\nSecret methodology text that must never leave the machine.\n\n"
        "References\n"
        "[1] LeCun, Y., Bengio, Y., Hinton, G. Deep learning. Nature 2015. doi:10.1038/nature14539",
    )
    pdf_bytes = bytes(pdf.output())

    isolated = extract_references_section_from_pdf(io.BytesIO(pdf_bytes))
    assert "Secret methodology text" not in isolated
    assert "Deep learning" in isolated
    assert "10.1038/nature14539" in isolated


def test_isolate_references_from_tex_thebibliography():
    """Garante o isolamento do ambiente thebibliography em arquivos LaTeX (.tex) (RF01, RNF02)."""
    tex_doc = r"""
    \documentclass{article}
    \begin{document}
    \section{Introduction}
    Texto inédito confidencial do artigo em LaTeX.
    \begin{thebibliography}{9}
    \bibitem{lecun2015} Y. LeCun, Y. Bengio, and G. Hinton, ``Deep learning,'' \emph{Nature}, 2015.
    \end{thebibliography}
    \end{document}
    """
    isolated = isolate_references_from_tex(tex_doc)
    assert "Texto inédito confidencial" not in isolated
    assert r"\bibitem{lecun2015}" in isolated
    assert "Deep learning" in isolated


def test_parse_bibtex_entries_deterministic_types_and_fields(tmp_path):
    """Testa a extração de campos padronizados (RF03) e tipos documentais (RN05) de arquivo .bib."""
    bib_path = tmp_path / "test.bib"
    bib_content = """
    @article{k1,
      author = {LeCun, Yann and Bengio, Yoshua},
      title = {{Deep learning}},
      journal = {Nature},
      year = {2015},
      doi = {https://doi.org/10.1038/nature14539}
    }
    @techreport{k2,
      author = {ABNT},
      title = {ABNT NBR 6023: Informacao e documentacao},
      year = {2018}
    }
    """
    bib_path.write_text(bib_content, encoding="utf-8")
    parsed = parse_bibtex_entries_deterministic(bib_content)

    assert len(parsed) == 2
    assert parsed[0].titulo == "Deep learning"
    assert parsed[0].doi == "10.1038/nature14539"
    assert parsed[0].ano == 2015
    assert parsed[0].autores == ["LeCun, Yann", "Bengio, Yoshua"]
    assert parsed[0].tipo_inferido == ReferenceType.ARTICLE

    assert parsed[1].tipo_inferido == ReferenceType.STANDARD
