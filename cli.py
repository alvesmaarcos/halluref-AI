"""Interface de Linha de Comando (CLI) para o Agente de Auditoria Bibliográfica (ALUC)."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from aluc.agent.auditor_agent import BibliographicAuditorAgent
from aluc.config import AlucConfig
from aluc.exporters import (
    export_report_to_json,
    export_report_to_markdown,
    export_report_to_pdf,
)
from aluc.schemas import VerdictStatus


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aluc",
        description="ALUC — Agente de IA para Auditoria e Detecção de Alucinações Bibliográficas",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit_cmd = subparsers.add_parser(
        "audit",
        help="Audita um arquivo acadêmico (.pdf, .bib ou .tex) e exporta relatórios.",
    )
    audit_cmd.add_argument(
        "file",
        type=str,
        help="Caminho para o arquivo de entrada (.pdf, .bib ou .tex).",
    )
    audit_cmd.add_argument(
        "--output-dir",
        type=str,
        default="./reports",
        help="Diretório de saída para salvar os relatórios (padrão: ./reports).",
    )
    audit_cmd.add_argument(
        "--format",
        choices=["md", "json", "pdf", "all"],
        default="all",
        help="Formato de exportação do relatório.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    console = Console()

    if args.command == "audit":
        input_path = Path(args.file)
        if not input_path.exists():
            console.print(f"[bold red]Erro:[/bold red] Arquivo não encontrado: {input_path}")
            return 1

        cfg = AlucConfig.from_env()
        agent = BibliographicAuditorAgent(config=cfg)

        console.print(
            Panel.fit(
                f"[bold cyan]ALUC — Iniciando Auditoria Bibliográfica[/bold cyan]\n"
                f"Arquivo: [yellow]{input_path}[/yellow]\n"
                f"Modelo Gemini: [green]{cfg.gemini_model}[/green]"
            )
        )

        def _cli_progress(current: int, total: int, msg: str) -> None:
            console.print(f"[dim]({current}/{total})[/dim] {msg}")

        report = agent.audit_file(input_path, progress_callback=_cli_progress)

        # Exibe tabela de resumo quantitativo
        summary_table = Table(title="Resumo Quantitativo")
        summary_table.add_column("Total Analisado", justify="center", style="bold")
        summary_table.add_column("VÁLIDAS", justify="center", style="green")
        summary_table.add_column("SUSPEITAS (Revisar)", justify="center", style="yellow")
        summary_table.add_column("ALUCINADAS", justify="center", style="red")
        summary_table.add_row(
            str(report.total_analisado),
            str(report.total_valido),
            str(report.total_suspeito),
            str(report.total_alucinado),
        )
        console.print(summary_table)

        # Exibe tabela de vereditos por referência
        detail_table = Table(title="Matriz de Decisão por Referência")
        detail_table.add_column("#", justify="right")
        detail_table.add_column("Título Citado", max_width=48)
        detail_table.add_column("Similaridade", justify="right")
        detail_table.add_column("Autoria", justify="center")
        detail_table.add_column("Status Final", justify="center")
        detail_table.add_column("Taxonomia", max_width=36)

        for res in report.resultados:
            if res.status_final == VerdictStatus.VALIDA:
                color = "green"
            elif res.status_final == VerdictStatus.SUSPEITA:
                color = "yellow"
            else:
                color = "red"

            detail_table.add_row(
                str(res.indice),
                res.referencia_extraida.titulo or "Sem título",
                f"{res.metricas.similaridade_titulo_pct:.1f}%",
                res.metricas.correspondencia_autoria,
                f"[{color}]{res.status_final.value}[/{color}]",
                res.categoria_taxonomia.value,
            )
        console.print(detail_table)

        # Salva relatórios conforme formato solicitado
        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        stem = input_path.stem

        saved_files: list[Path] = []
        if args.format in {"md", "all"}:
            md_path = out_dir / f"relatorio_{stem}.md"
            export_report_to_markdown(report, md_path)
            saved_files.append(md_path)
        if args.format in {"json", "all"}:
            json_path = out_dir / f"relatorio_{stem}.json"
            export_report_to_json(report, json_path)
            saved_files.append(json_path)
        if args.format in {"pdf", "all"}:
            pdf_path = out_dir / f"relatorio_{stem}.pdf"
            export_report_to_pdf(report, pdf_path)
            saved_files.append(pdf_path)

        console.print("\n[bold green]Relatórios exportados com sucesso:[/bold green]")
        for p in saved_files:
            console.print(f" - {p.resolve()}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
