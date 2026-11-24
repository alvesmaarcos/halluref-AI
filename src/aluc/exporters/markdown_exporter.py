"""Exportador de relatório de auditoria bibliográfica para Markdown (RF06)."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Union

from aluc.schemas import AuditReport, VerdictStatus


def _status_badge(status: VerdictStatus) -> str:
    if status == VerdictStatus.VALIDA:
        return "VÁLIDA"
    if status == VerdictStatus.SUSPEITA:
        return "SUSPEITA (Revisar)"
    return "ALUCINADA"


def export_report_to_markdown(
    report: AuditReport, output_path: Optional[Union[str, Path]] = None
) -> str:
    """Gera o relatório completo de auditoria em formato Markdown (RF06)."""
    report.recompute_totals()

    lines: List[str] = [
        "# Relatório de Auditoria e Detecção de Alucinações Bibliográficas",
        "",
        f"- **Arquivo Analisado:** `{report.arquivo_origem}` ({report.formato_origem})",
        f"- **Data/Hora da Auditoria:** `{report.data_hora_iso}`",
        "",
        f"- {report.gemini_summary}",
        *(f"- {warning}" for warning in report.avisos),
        "",
        "## 1. Resumo Quantitativo",
        "",
        "| Métrica | Quantidade | Percentual |",
        "| :--- | :---: | :---: |",
    ]

    total = max(1, report.total_analisado)
    lines.extend(
        [
            f"| **Total Analisado** | **{report.total_analisado}** | 100.0% |",
            f"| **Total Válido (VÁLIDA)** | {report.total_valido} | {(report.total_valido / total) * 100:.1f}% |",
            f"| **Total Suspeito (SUSPEITA - Revisar)** | {report.total_suspeito} | {(report.total_suspeito / total) * 100:.1f}% |",
            f"| **Total Alucinado (ALUCINADA)** | {report.total_alucinado} | {(report.total_alucinado / total) * 100:.1f}% |",
            "",
            "---",
            "",
            "## 2. Matriz Geral de Vereditos",
            "",
            "| # | Título Citado | Ano | DOI Citado | Similaridade | Autoria | Status Final | Taxonomia |",
            "| :-: | :--- | :-: | :--- | :---: | :---: | :---: | :--- |",
        ]
    )

    for res in report.resultados:
        ref = res.referencia_extraida
        m = res.metricas
        short_title = (
            ref.titulo[:65] + "..." if len(ref.titulo) > 65 else (ref.titulo or "Sem título")
        ).replace("|", "/")
        doi_str = f"`{ref.doi}`" if ref.doi else "—"
        year_str = str(ref.ano) if ref.ano else "—"
        sim_str = f"{m.similaridade_titulo_pct:.1f}%"
        lines.append(
            f"| {res.indice} | {short_title} | {year_str} | {doi_str} | "
            f"{sim_str} | {m.correspondencia_autoria} | **{_status_badge(res.status_final)}** | "
            f"{res.categoria_taxonomia.value} |"
        )

    lines.extend(["", "---", "", "## 3. Diagnóstico Explicativo Detalhado", ""])

    for res in report.resultados:
        ref = res.referencia_extraida
        m = res.metricas
        off = res.melhor_correspondencia_oficial

        lines.extend(
            [
                f"### [{res.indice}] {ref.titulo or 'Referência sem título extraído'}",
                "",
                f"- **Status Final:** `{res.status_final.value}`",
                f"- **Classificação na Taxonomia:** {res.categoria_taxonomia.value}",
                f"- **Diagnóstico Explicativo:** {res.diagnostico_explicativo}",
                f"- **Ação Recomendada:** {res.acao_recomendada}",
                "",
                "#### Metadados Extraídos vs. Registro Oficial Encontrado",
                "",
                "| Campo | Citado no Documento | Registro Oficial (API) |",
                "| :--- | :--- | :--- |",
                f"| **Título** | {ref.titulo or '—'} | {off.titulo_oficial if off else 'Não encontrado'} |",
                f"| **Autores** | {', '.join(ref.autores) if ref.autores else '—'} | {', '.join(off.autores_oficiais) if (off and off.autores_oficiais) else '—'} |",
                f"| **Ano** | {ref.ano or '—'} | {off.ano_oficial if (off and off.ano_oficial) else '—'} |",
                f"| **Veículo** | {ref.veiculo or '—'} | {off.veiculo_oficial if (off and off.veiculo_oficial) else '—'} |",
                f"| **DOI** | {ref.doi or '—'} | {off.doi_oficial if (off and off.doi_oficial) else '—'} |",
                f"| **Base / Fonte** | Documento ({report.formato_origem}) | {off.fonte_api if off else 'Nenhuma correspondência'} |",
                "",
                f"- **Métricas Calculadas:** Similaridade de Título = `{m.similaridade_titulo_pct:.1f}%` (`{m.faixa_similaridade_titulo}`) | "
                f"Interseção de Autoria = `{m.correspondencia_autoria}` | Status DOI = `{m.doi_status}` | "
                f"Diferença Temporal = `{m.diferenca_ano if m.diferenca_ano is not None else 'N/A'}` ano(s) | "
                f"Exceção de Escopo = `{'Sim (' + (m.motivo_rn05 or '') + ')' if m.excecao_escopo_rn05 else 'Não'}`",
            ]
        )

        if res.falhas_consulta:
            lines.append(f"- **Falhas de consulta:** {', '.join(res.falhas_consulta)}")
        if res.estado_investigacao:
            lines.append(f"- **Investigação:** {res.estado_investigacao}")
        if res.correcao_verificada:
            lines.extend([
                f"- **Correção:** {res.correcao_verificada.citation}",
                "",
                "```bibtex",
                res.correcao_verificada.bibtex,
                "```",
            ])

        if res.rastro_tools:
            lines.append("- **Rastro de Consultas do Agente (Tools):**")
            for trace in res.rastro_tools:
                lines.append(f"  - `{trace.tool_name}`: {trace.summary_result}")

        lines.extend(["", "---", ""])

    md_content = "\n".join(lines)
    if output_path is not None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(md_content, encoding="utf-8")

    return md_content
