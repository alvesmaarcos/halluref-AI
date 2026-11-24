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


def test_extract_pdf_with_spaced_heading_and_inline_first_reference():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(
        0,
        8,
        "Unpublished manuscript text.\n"
        "VII. R E F E R E N C E S: [1] Miller, A. (2024). An empirical study.\n"
        "[2] Wong, B. (2020). Related work in science.\n"
        "Appendix A Supplementary results\nPrivate results.",
    )

    isolated = extract_references_section_from_pdf(bytes(pdf.output()))

    assert isolated.startswith("[1] Miller")
    assert "[2] Wong" in isolated
    assert "Unpublished" not in isolated
    assert "Private results" not in isolated


def test_locates_numbered_bibliography_without_heading():
    text = (
        "Private manuscript text.\n"
        "[1] Miller, A. (2024). An empirical study.\n"
        "[2] Wong, B. (2020). Related work in science.\n"
        "[3] Tan, E. (2019). Results in another field.\n"
        "Private author notes."
    )

    isolated = isolate_references_from_text(text)

    assert isolated.startswith("[1] Miller")
    assert isolated.endswith("another field.")
    assert "Private" not in isolated


def test_does_not_extract_bibliography_from_contents_or_short_numbered_list():
    text = (
        "Table of contents\nReferences\nIntroduction\n"
        "References to private materials appear below.\n"
        "[1] Internal results recorded by researchers in 2024.\n"
        "[2] Internal list of participants in 2025."
    )

    assert isolate_references_from_text(text) == ""


def test_image_only_pdf_uses_local_ocr_before_extracting(monkeypatch):
    from aluc.ingestion import pdf_extractor

    pdf = FPDF()
    pdf.add_page()
    events = []

    def recognize(data):
        assert data.startswith(b"%PDF")
        assert "OCR local" in events[-1]
        return [
            "Private manuscript text.",
            "REFERENCES\n[IJ Miller, A. (2024). An empirical study.\n121 Wong, B. (2020). Related work.\n2/2",
        ]

    monkeypatch.setattr(pdf_extractor, "recognize_pdf_bytes", recognize)
    isolated = extract_references_section_from_pdf(bytes(pdf.output()), notify=events.append)

    assert isolated == "[1] Miller, A. (2024). An empirical study.\n[2] Wong, B. (2020). Related work."


def test_pdf_numbering_gap_triggers_one_assisted_extraction():
    from types import SimpleNamespace

    from aluc.agent.parser_agent import SemanticReferenceParser
    from aluc.config import AlucConfig

    parser = SemanticReferenceParser(AlucConfig())
    events = []
    calls = []

    def extract(**kwargs):
        calls.append(kwargs)
        assert "estruturar a bibliografia" in events[-1]
        return SimpleNamespace(output_text="""{"referencias": [
            {"titulo": "An empirical study", "texto_original": "[1] Miller"},
            {"titulo": "Related manuscript", "texto_original": "[2] Wong"},
            {"titulo": "Another field", "texto_original": "[3] Tan"}
        ]}""")

    parser.client = SimpleNamespace(interactions=SimpleNamespace(create=extract))
    references = parser.parse_references(
        "[1] Miller (2024). An empirical study. Journal.\n"
        "Wong (2020). Related manuscript. Journal.\n"
        "[3] Tan (2019). Another field. Journal.",
        before_gemini=events.append,
    )

    assert len(calls) == 1
    assert len(references) == 3


def test_ocr_year_does_not_make_correct_coauthor_suspicious():
    from aluc.agent.parser_agent import SemanticReferenceParser
    from aluc.config import AlucConfig
    from aluc.rules.metrics import compute_comparison_metrics, evaluate_decision_matrix
    from aluc.schemas import OfficialWorkMetadata, VerdictStatus

    title = (
        "Comparative Reflections on Human-Driven and Generative Artificial Intelligence-Assisted "
        "Thematic Analysis: A Collaborative Autoethnography"
    )
    parser = SemanticReferenceParser(AlucConfig())
    [reference] = parser.parse_references(
        f"[1] Anas Al-Fattal and Jasvir Singh- 2025. {title}. "
        "International Journal of Qualitative Methods."
    )
    official = OfficialWorkMetadata(
        fonte_api="Crossref",
        titulo_oficial=title,
        autores_oficiais=["Anas Al-Fattal", "Jasvir Singh"],
        ano_oficial=2025,
    )
    metrics = compute_comparison_metrics(reference, official)

    assert reference.autores == ["Anas Al-Fattal", "Jasvir Singh"]
    assert reference.ano == 2025
    assert metrics.intersecao_demais_autores_pct == 100.0
    assert evaluate_decision_matrix(metrics)[0] == VerdictStatus.VALIDA


def test_acm_year_boundary_preserves_author_initials():
    from aluc.agent.parser_agent import _heuristic_parse_plain_references

    [reference] = _heuristic_parse_plain_references(
        "[1] He Zhang and John M. Carroll. 2025. Harnessing AI in research. A journal."
    )

    assert reference.autores == ["He Zhang", "John M. Carroll"]
    assert reference.titulo == "Harnessing AI in research"
