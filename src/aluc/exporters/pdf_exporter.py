"""Exportador de relatório de auditoria bibliográfica para PDF usando fpdf2 (RF06)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union
from fpdf import FPDF

from aluc.schemas import AuditReport, VerdictStatus


def _sanitize_latin1(text: str) -> str:
    """Garante compatibilidade de caracteres com as fontes padrão Helvetica do PDF (CP1252/Latin-1)."""
    if not text:
        return ""
    replacements = {
        "\u2013": "-",
        "\u2014": "--",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2026": "...",
        "\u2192": "->",
        "\u2265": ">=",
        "\u2264": "<=",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text.encode("latin-1", errors="replace").decode("latin-1")


class AuditPDFDocument(FPDF):
    """Documento PDF formatado para o Relatório de Auditoria ALUC."""

    def header(self) -> None:
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(40, 55, 80)
        self.cell(
            0,
            8,
            _sanitize_latin1(
                "ALUC - Relatorio de Auditoria e Deteccao de Alucinacoes Bibliograficas"
            ),
            new_x="LMARGIN",
            new_y="NEXT",
            align="L",
        )
        self.set_draw_color(180, 190, 205)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(4)

    def footer(self) -> None:
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(
            0,
            10,
            _sanitize_latin1(f"Pagina {self.page_no()}/{{nb}}"),
            align="C",
        )


def export_report_to_pdf(
    report: AuditReport, output_path: Optional[Union[str, Path]] = None
) -> bytes:
    """Gera o relatório de auditoria em PDF (RF06) e retorna os bytes do arquivo."""
    report.recompute_totals()

    pdf = AuditPDFDocument(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.alias_nb_pages()
    pdf.add_page()

    # Título principal e metadados da execução
    pdf.set_font("Helvetica", "B", 15)
    pdf.set_text_color(20, 30, 50)
    pdf.cell(
        0,
        10,
        _sanitize_latin1("Relatorio de Auditoria Bibliografica"),
        new_x="LMARGIN",
        new_y="NEXT",
    )

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(60, 60, 60)
    pdf.cell(
        0,
        6,
        _sanitize_latin1(
            f"Arquivo: {report.arquivo_origem} ({report.formato_origem})  |  Data/Hora: {report.data_hora_iso}"
        ),
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(3)

    # 1. Resumo Quantitativo
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(20, 30, 50)
    pdf.cell(
        0,
        8,
        _sanitize_latin1("1. Resumo Quantitativo"),
        new_x="LMARGIN",
        new_y="NEXT",
    )

    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(235, 240, 248)
    summary_text = (
        f"Total Analisado: {report.total_analisado}   |   "
        f"Validas: {report.total_valido}   |   "
        f"Suspeitas (Revisar): {report.total_suspeito}   |   "
        f"Alucinadas: {report.total_alucinado}"
    )
    pdf.cell(
        0,
        9,
        _sanitize_latin1(summary_text),
        border=1,
        fill=True,
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(5)

    pdf.set_font("Helvetica", "", 9)
    for text in [report.gemini_summary, *report.avisos]:
        pdf.multi_cell(0, 5, _sanitize_latin1(text), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    # 2. Detalhamento por Referência
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(
        0,
        8,
        _sanitize_latin1("2. Diagnostico Detalhado por Referencia"),
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(2)

    for res in report.resultados:
        ref = res.referencia_extraida
        m = res.metricas
        off = res.melhor_correspondencia_oficial

        # Define cores semafóricas por status
        if res.status_final == VerdictStatus.VALIDA:
            bg_r, bg_g, bg_b = 225, 245, 230
            txt_r, txt_g, txt_b = 20, 110, 45
        elif res.status_final == VerdictStatus.SUSPEITA:
            bg_r, bg_g, bg_b = 255, 246, 215
            txt_r, txt_g, txt_b = 150, 100, 0
        else:
            bg_r, bg_g, bg_b = 253, 228, 228
            txt_r, txt_g, txt_b = 165, 25, 25

        pdf.set_fill_color(bg_r, bg_g, bg_b)
        pdf.set_text_color(txt_r, txt_g, txt_b)
        pdf.set_font("Helvetica", "B", 10)
        header_line = (
            f"[{res.indice}] {res.status_final.value} - {res.categoria_taxonomia.value}"
        )
        pdf.multi_cell(
            0,
            7,
            _sanitize_latin1(header_line),
            border=1,
            fill=True,
            new_x="LMARGIN",
            new_y="NEXT",
        )

        pdf.set_text_color(30, 30, 30)
        pdf.set_font("Helvetica", "B", 9)
        pdf.multi_cell(
            0,
            5,
            _sanitize_latin1(f"Titulo Citado: {ref.titulo or 'Nao identificado'}"),
            new_x="LMARGIN",
            new_y="NEXT",
        )

        pdf.set_font("Helvetica", "", 9)
        authors_str = ", ".join(ref.autores) if ref.autores else "Nao informados"
        meta_line = (
            f"Autores Citados: {authors_str} | Ano: {ref.ano or 's/d'} | "
            f"DOI: {ref.doi or 'Ausente'} | Similaridade: {m.similaridade_titulo_pct:.1f}% ({m.faixa_similaridade_titulo})"
        )
        pdf.multi_cell(
            0, 5, _sanitize_latin1(meta_line), new_x="LMARGIN", new_y="NEXT"
        )

        if off is not None:
            off_authors = ", ".join(off.autores_oficiais[:4]) or "Nao informados"
            off_line = (
                f"Correspondencia Oficial ({off.fonte_api}): '{off.titulo_oficial}' "
                f"({off_authors}, {off.ano_oficial or 's/d'}) [DOI: {off.doi_oficial or 'N/A'}]"
            )
            pdf.multi_cell(
                0, 5, _sanitize_latin1(off_line), new_x="LMARGIN", new_y="NEXT"
            )

        pdf.set_font("Helvetica", "I", 9)
        pdf.multi_cell(
            0,
            5,
            _sanitize_latin1(f"Diagnostico: {res.diagnostico_explicativo}"),
            new_x="LMARGIN",
            new_y="NEXT",
        )

        pdf.set_font("Helvetica", "B", 9)
        pdf.multi_cell(
            0,
            5,
            _sanitize_latin1(f"Acao Recomendada: {res.acao_recomendada}"),
            new_x="LMARGIN",
            new_y="NEXT",
        )
        investigation_lines = []
        if res.falhas_consulta:
            investigation_lines.append("Falhas de consulta: " + ", ".join(res.falhas_consulta))
        if res.estado_investigacao:
            investigation_lines.append(res.estado_investigacao)
        if res.correcao_verificada:
            investigation_lines.extend([res.correcao_verificada.citation, res.correcao_verificada.bibtex])
        pdf.set_font("Helvetica", "", 9)
        for text in investigation_lines:
            pdf.multi_cell(0, 5, _sanitize_latin1(text), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

    pdf_bytes = bytes(pdf.output())
    if output_path is not None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(pdf_bytes)

    return pdf_bytes
