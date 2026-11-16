"""Interface Web Streamlit para o Agente de Auditoria e Detecção de Alucinações Bibliográficas (ALUC)."""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile

# Garante que o pacote em src/ esteja acessível ao rodar `streamlit run app.py`
ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import streamlit as st

from aluc.agent.auditor_agent import BibliographicAuditorAgent
from aluc.config import AlucConfig
from aluc.exporters import (
    export_report_to_json,
    export_report_to_markdown,
    export_report_to_pdf,
)
from aluc.schemas import AuditReport, VerdictStatus

st.set_page_config(
    page_title="ALUC — Auditoria de Alucinações Bibliográficas",
    page_icon="🔍",
    layout="wide",
)

st.title("🔍 ALUC — Agente de IA para Auditoria e Detecção de Alucinações Bibliográficas")
st.markdown(
    "Validação automatizada de citações acadêmicas (`.pdf`, `.bib`, `.tex`) via **Gemini 3.8 Flash (Tool-Calling)** "
    "em cascata nas bases **Crossref**, **OpenAlex** e **Semantic Scholar**."
)

# Barra lateral de configurações
with st.sidebar:
    st.header("⚙️ Configuração do Agente")
    env_cfg = AlucConfig.from_env()

    api_key_input = st.text_input(
        "GEMINI_API_KEY (Google AI Studio)",
        value=env_cfg.gemini_api_key,
        type="password",
        help="Chave do Google AI Studio para o parser semântico e agente Tool-Calling.",
    )
    model_input = st.selectbox(
        "Modelo Gemini (Interactions API)",
        options=["gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-4-argon"],
        index=0,
    )

    st.divider()
    st.markdown("### 📋 Critérios de Auditoria Ativos")
    st.caption(
        "- **Validação de DOI:** Resolução prioritária de DOI (detecção de erro 404 e DOI cruzado)\n"
        "- **Similaridade de Título:** $\ge 85\%$ Forte | $60\text{--}84\%$ Parcial | $<60\%$ Ausente\n"
        "- **Interseção de Autoria:** Validação dos sobrenomes dos autores (anti-quimera)\n"
        "- **Tolerância Temporal:** Diferença aceitável de até $\pm 2$ anos\n"
        "- **Exceções de Escopo:** Normas técnicas (ABNT/ISO), leis, URLs e literatura cinzenta\n"
        "- **Privacidade do Manuscrito:** Isolamento local da seção de referências"
    )

col_upload, col_demo = st.columns([3, 1])

with col_upload:
    uploaded_file = st.file_uploader(
        "Envie seu manuscrito ou arquivo de referências (.pdf, .bib, .tex)",
        type=["pdf", "bib", "tex"],
    )

with col_demo:
    st.write("")
    st.write("")
    load_sample = st.button(
        "🧪 Carregar Caso de Teste Completo (.bib)",
        use_container_width=True,
        help="Carrega o arquivo de demonstração contendo exemplos reais e os 5 padrões clássicos de alucinação.",
    )

target_path: Path | None = None
display_filename: str = ""

if load_sample:
    sample_bib = ROOT_DIR / "tests" / "fixtures" / "sample_references.bib"
    if sample_bib.exists():
        st.session_state["demo_mode"] = True

if uploaded_file is not None:
    st.session_state["demo_mode"] = False
    tmp_dir = Path(tempfile.gettempdir()) / "aluc_uploads"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    target_path = tmp_dir / uploaded_file.name
    target_path.write_bytes(uploaded_file.getvalue())
    display_filename = uploaded_file.name
elif st.session_state.get("demo_mode"):
    sample_bib = ROOT_DIR / "tests" / "fixtures" / "sample_references.bib"
    if sample_bib.exists():
        target_path = sample_bib
        display_filename = sample_bib.name
        st.info(f"Arquivo de demonstração carregado: `{display_filename}`")

if target_path is not None:
    run_audit = st.button("🚀 Executar Auditoria Bibliográfica", type="primary")

    if run_audit:
        cfg = AlucConfig.from_env(
            api_key_override=api_key_input,
            model_override=model_input,
        )
        agent = BibliographicAuditorAgent(config=cfg)

        progress_bar = st.progress(0, text="Isolando seção de referências...")
        status_box = st.empty()

        def _on_progress(current: int, total: int, message: str) -> None:
            pct = int((current / max(1, total)) * 100)
            progress_bar.progress(pct, text=message)
            status_box.caption(message)

        report = agent.audit_file(target_path, progress_callback=_on_progress)
        progress_bar.progress(100, text="Auditoria concluída com sucesso!")
        status_box.empty()
        st.session_state["last_report"] = report

report: AuditReport | None = st.session_state.get("last_report")

if report is not None:
    st.divider()

    # Pré-visualização de Privacidade
    with st.expander("🔒 Privacidade do Manuscrito — Seção de Referências Isolada Localmente"):
        st.caption(
            "Apenas o bloco abaixo foi extraído para análise. O corpo do artigo (introdução, metodologia, resultados) "
            "não é enviado para APIs externas."
        )
        st.code(report.secao_referencias_isolada_preview, language="text")

    # Resumo Quantitativo
    st.subheader("📊 Resumo Quantitativo da Auditoria")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Analisado", report.total_analisado)
    m2.metric("✅ Válidas", report.total_valido)
    m3.metric("⚠️ Suspeitas (Revisar)", report.total_suspeito)
    m4.metric("🚨 Alucinadas", report.total_alucinado)

    # Botões de Exportação
    st.subheader("📥 Exportar Relatório de Diagnóstico")
    md_str = export_report_to_markdown(report)
    json_str = export_report_to_json(report)
    pdf_bytes = export_report_to_pdf(report)

    dl1, dl2, dl3 = st.columns(3)
    stem = Path(report.arquivo_origem).stem
    with dl1:
        st.download_button(
            "⬇️ Baixar Relatório Markdown (.md)",
            data=md_str.encode("utf-8"),
            file_name=f"relatorio_auditoria_{stem}.md",
            mime="text/markdown",
            use_container_width=True,
        )
    with dl2:
        st.download_button(
            "⬇️ Baixar Relatório JSON (.json)",
            data=json_str.encode("utf-8"),
            file_name=f"relatorio_auditoria_{stem}.json",
            mime="application/json",
            use_container_width=True,
        )
    with dl3:
        st.download_button(
            "⬇️ Baixar Relatório PDF (.pdf)",
            data=pdf_bytes,
            file_name=f"relatorio_auditoria_{stem}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

    st.divider()
    st.subheader("🔎 Detalhamento e Diagnóstico Explicativo por Referência")

    status_filter = st.multiselect(
        "Filtrar por Veredito:",
        options=[
            VerdictStatus.VALIDA.value,
            VerdictStatus.SUSPEITA.value,
            VerdictStatus.ALUCINADA.value,
        ],
        default=[
            VerdictStatus.VALIDA.value,
            VerdictStatus.SUSPEITA.value,
            VerdictStatus.ALUCINADA.value,
        ],
    )

    for res in report.resultados:
        if res.status_final.value not in status_filter:
            continue

        ref = res.referencia_extraida
        m = res.metricas
        off = res.melhor_correspondencia_oficial

        if res.status_final == VerdictStatus.VALIDA:
            icon = "✅"
        elif res.status_final == VerdictStatus.SUSPEITA:
            icon = "⚠️"
        else:
            icon = "🚨"

        header = (
            f"{icon} [{res.indice}] {res.status_final.value} — "
            f"{ref.titulo or 'Sem título'} ({ref.ano or 's/d'})"
        )
        with st.expander(header, expanded=(res.status_final != VerdictStatus.VALIDA)):
            st.markdown(f"**Categoria na Taxonomia:** `{res.categoria_taxonomia.value}`")
            st.markdown(f"**Diagnóstico Explicativo:** {res.diagnostico_explicativo}")
            st.markdown(f"**Ação Recomendada:** *{res.acao_recomendada}*")

            c1, c2 = st.columns(2)
            with c1:
                st.markdown("##### 📄 Citado no Documento")
                st.write(f"- **Título:** {ref.titulo or '—'}")
                st.write(
                    f"- **Autores:** {', '.join(ref.autores) if ref.autores else '—'}"
                )
                st.write(f"- **Ano:** {ref.ano or '—'}")
                st.write(f"- **Veículo:** {ref.veiculo or '—'}")
                st.write(f"- **DOI:** `{ref.doi}`" if ref.doi else "- **DOI:** —")
                st.write(f"- **Tipo Inferido:** `{ref.tipo_inferido.value}`")

            with c2:
                st.markdown("##### 🌐 Melhor Correspondência Oficial (APIs)")
                if off is not None:
                    st.write(f"- **Fonte:** `{off.fonte_api}`")
                    st.write(f"- **Título Oficial:** {off.titulo_oficial}")
                    st.write(
                        f"- **Autores Oficiais:** {', '.join(off.autores_oficiais) if off.autores_oficiais else '—'}"
                    )
                    st.write(f"- **Ano Oficial:** {off.ano_oficial or '—'}")
                    st.write(f"- **Veículo Oficial:** {off.veiculo_oficial or '—'}")
                    st.write(
                        f"- **DOI Oficial:** `{off.doi_oficial}`"
                        if off.doi_oficial
                        else "- **DOI Oficial:** —"
                    )
                else:
                    st.warning("Nenhum registro compatível encontrado nas bases consultadas.")

            st.caption(
                f"Métricas Calculadas: Similaridade de Título = {m.similaridade_titulo_pct:.1f}% ({m.faixa_similaridade_titulo}) | "
                f"Autoria = {m.correspondencia_autoria} (1º autor: {'Sim' if m.primeiro_autor_coincide else 'Não'}, "
                f"Demais: {m.intersecao_demais_autores_pct:.0f}%) | Status DOI = {m.doi_status} | "
                f"Delta Ano = {m.diferenca_ano if m.diferenca_ano is not None else 'N/A'}"
            )

            if res.rastro_tools:
                st.markdown("**🛠️ Rastro de Execução de Tools do Agente:**")
                for trace in res.rastro_tools:
                    st.code(f"[{trace.tool_name}] -> {trace.summary_result}", language="text")
