"""Testes unitários para os exportadores de relatórios em Markdown, JSON e PDF (RF06)."""

import json
from aluc.exporters import (
    export_report_to_json,
    export_report_to_markdown,
    export_report_to_pdf,
)
from aluc.schemas import (
    AuditReport,
    ComparisonMetrics,
    HallucinationCategory,
    ParsedReference,
    ReferenceAuditResult,
    VerdictStatus,
)


def _sample_report() -> AuditReport:
    res = ReferenceAuditResult(
        indice=1,
        referencia_extraida=ParsedReference(
            texto_original="Silva (2024) Artigo Fantasma",
            titulo="Artigo Fantasma sobre Redes Neurais Quânticas",
            autores=["Silva, João"],
            ano=2024,
        ),
        status_final=VerdictStatus.ALUCINADA,
        categoria_taxonomia=HallucinationCategory.GHOST_REFERENCE,
        diagnostico_explicativo="Obra não encontrada no Crossref, OpenAlex e Semantic Scholar.",
        acao_recomendada="Remover a referência do artigo.",
        metricas=ComparisonMetrics(similaridade_titulo_pct=18.5),
    )
    report = AuditReport(
        arquivo_origem="artigo_teste.pdf",
        formato_origem="PDF",
        data_hora_iso="2026-11-10T12:00:00Z",
        resultados=[res],
    )
    report.recompute_totals()
    return report


def test_export_markdown_json_and_pdf(tmp_path):
    """Verifica geração e gravação em disco dos formatos .md, .json e .pdf (RF06)."""
    report = _sample_report()

    md_path = tmp_path / "relatorio.md"
    json_path = tmp_path / "relatorio.json"
    pdf_path = tmp_path / "relatorio.pdf"

    md_text = export_report_to_markdown(report, md_path)
    json_text = export_report_to_json(report, json_path)
    pdf_bytes = export_report_to_pdf(report, pdf_path)

    assert md_path.exists()
    assert "Resumo Quantitativo" in md_text
    assert "Artigo Fantasma sobre Redes Neurais Quânticas" in md_text

    assert json_path.exists()
    parsed_json = json.loads(json_text)
    assert parsed_json["total_analisado"] == 1
    assert parsed_json["total_alucinado"] == 1

    assert pdf_path.exists()
    assert pdf_bytes.startswith(b"%PDF")
