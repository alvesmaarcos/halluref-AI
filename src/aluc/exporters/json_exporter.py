"""Exportador de relatório de auditoria bibliográfica para JSON (RF06)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

from aluc.schemas import AuditReport


def export_report_to_json(
    report: AuditReport, output_path: Optional[Union[str, Path]] = None
) -> str:
    """Serializa o AuditReport em JSON formatado (UTF-8) e salva em disco se output_path for informado."""
    report.recompute_totals()
    json_str = report.model_dump_json(indent=2)
    if output_path is not None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json_str, encoding="utf-8")
    return json_str
