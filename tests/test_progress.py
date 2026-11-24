"""Verifica a apresentação do progresso nas interfaces de auditoria."""

from pathlib import Path
import runpy
import sys
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import cli
from aluc.agent import auditor_agent
from aluc.schemas import (
    AuditReport,
    HallucinationCategory,
    ParsedReference,
    ReferenceAuditResult,
    VerdictStatus,
)


def _report():
    return AuditReport(
        arquivo_origem="sample_references.bib",
        formato_origem="BIB",
        data_hora_iso="2026-01-01",
    )


def test_cli_reports_progress_before_export(monkeypatch, tmp_path, capsys):
    class Agent:
        def __init__(self, config):
            pass

        def audit_file(self, path, progress_callback):
            progress_callback(1, 2, "Referência 1/2 · Aguardando resposta do Crossref")
            assert "Aguardando resposta do Crossref" in capsys.readouterr().out
            return _report()

    def export(report, path):
        assert "Gerando relatório JSON" in capsys.readouterr().out

    monkeypatch.setattr(cli, "BibliographicAuditorAgent", Agent)
    monkeypatch.setattr(cli, "export_report_to_json", export)

    assert cli.main([
        "audit", "tests/fixtures/sample_references.bib", "--format", "json",
        "--output-dir", str(tmp_path),
    ]) == 0
    assert "exportados com sucesso" in capsys.readouterr().out


@pytest.mark.parametrize("fails", [False, True])
def test_streamlit_keeps_status_running_during_wait(monkeypatch, fails):
    events = []
    streamlit = MagicMock()
    streamlit.session_state = {}
    streamlit.columns.side_effect = lambda layout: [
        MagicMock() for _ in range(layout if isinstance(layout, int) else len(layout))
    ]
    streamlit.file_uploader.return_value = None
    streamlit.button.return_value = True
    streamlit.text_input.return_value = ""
    streamlit.selectbox.return_value = "placeholder"
    streamlit.multiselect.return_value = []

    def tracked_status(label, *, state):
        events.append((label, state))
        widget = MagicMock()
        widget.update.side_effect = lambda *, label, state=None: events.append((label, state))
        return widget

    streamlit.status.side_effect = tracked_status

    class Agent:
        def __init__(self, config):
            pass

        def audit_file(self, path, progress_callback):
            message = "Referência 1/2 · Aguardando resposta do Crossref"
            progress_callback(1, 2, message)
            assert events[-1] == (message, None)
            assert events[0][1] == "running"
            time.sleep(0.01)
            if fails:
                raise RuntimeError("Falha simulada")
            return _report()

    monkeypatch.setitem(sys.modules, "streamlit", streamlit)
    monkeypatch.setattr(auditor_agent, "BibliographicAuditorAgent", Agent)
    runpy.run_path(str(Path(cli.__file__).with_name("app.py")))

    assert events[-1][1] == ("error" if fails else "complete")
    if not fails:
        assert events[-2][0] == "Preparando relatórios para download…"


@pytest.mark.parametrize("selected", [[], [0]])
def test_streamlit_shows_details_only_for_selected_filtered_row(monkeypatch, selected):
    report = _report()
    report.resultados = [
        ReferenceAuditResult(
            indice=index,
            referencia_extraida=ParsedReference(titulo=title, texto_original=title),
            status_final=status,
            categoria_taxonomia=HallucinationCategory.NONE,
            diagnostico_explicativo=diagnosis,
            acao_recomendada="Conferir a fonte.",
        )
        for index, title, status, diagnosis in [
            (1, "Primeira obra", VerdictStatus.VALIDA, "Diagnóstico da primeira"),
            (2, "Segunda obra", VerdictStatus.SUSPEITA, "Diagnóstico da segunda"),
        ]
    ]
    streamlit = MagicMock()
    streamlit.session_state = {"last_run": (report, ("", "", b""))}
    streamlit.columns.side_effect = lambda layout: [
        MagicMock() for _ in range(layout if isinstance(layout, int) else len(layout))
    ]
    streamlit.file_uploader.return_value = None
    streamlit.button.return_value = False
    streamlit.multiselect.return_value = [VerdictStatus.SUSPEITA.value]
    streamlit.dataframe.return_value = SimpleNamespace(selection=SimpleNamespace(rows=selected))
    monkeypatch.setitem(sys.modules, "streamlit", streamlit)

    runpy.run_path(str(Path(cli.__file__).with_name("app.py")))

    assert streamlit.dataframe.call_args.args[0] == [
        {"Nº": 2, "Referência": "Segunda obra", "Status": VerdictStatus.SUSPEITA.value}
    ]
    assert streamlit.dataframe.call_args.kwargs["selection_mode"] == "single-row"
    diagnoses = [
        call.args[0] for call in streamlit.markdown.call_args_list
        if "Diagnóstico Explicativo" in call.args[0]
    ]
    assert diagnoses == (["**Diagnóstico Explicativo:** Diagnóstico da segunda"] if selected else [])
