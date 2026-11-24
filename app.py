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
from aluc.schemas import VerdictStatus

st.set_page_config(
    page_title="ALUC — Auditoria de Alucinações Bibliográficas",
    page_icon="🔍",
    layout="wide",
)

st.title("🔍 ALUC — Agente de IA para Auditoria e Detecção de Alucinações Bibliográficas")
st.markdown(
    "Validação de citações acadêmicas em Crossref, OpenAlex e Semantic Scholar, "
    "com investigação opcional em lote pelo Gemini."
)

# Barra lateral de configurações
with st.sidebar:
    st.header("⚙️ Configuração do Agente")
    env_cfg = AlucConfig.from_env()

    api_key_input = st.text_input(
        "GEMINI_API_KEY (Google AI Studio)",
        value=env_cfg.gemini_api_key,
        type="password",
        help="Chave opcional para extração assistida e investigação em lote. Até três chamadas por documento.",
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
        "- **Similaridade de Título:** ≥ 85% forte, de 60% a menos de 85% parcial e abaixo de 60% ausente\n"
        "- **Interseção de Autoria:** Validação dos sobrenomes dos autores (anti-quimera)\n"
        "- **Tolerância Temporal:** Diferença aceitável de até dois anos\n"
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
elif st.session_state.get("demo_mode"):
    sample_bib = ROOT_DIR / "tests" / "fixtures" / "sample_references.bib"
    if sample_bib.exists():
        target_path = sample_bib
        display_filename = sample_bib.name
        st.info(f"Arquivo de demonstração carregado: `{display_filename}`")

if uploaded_file is not None or target_path is not None:
    run_audit = st.button("🚀 Executar Auditoria Bibliográfica", type="primary")

    if run_audit:
        status = st.status("Iniciando auditoria…", state="running")

        def _on_progress(current: int, total: int, message: str) -> None:
            status.update(label=message)

        try:
            cfg = AlucConfig.from_env(
                api_key_override=api_key_input,
                model_override=model_input,
            )
            agent = BibliographicAuditorAgent(config=cfg)
            if uploaded_file is not None:
                status.update(label="Preparando o arquivo recebido…")
                with tempfile.TemporaryDirectory(prefix="aluc-") as tmp_dir:
                    staged_file = Path(tmp_dir) / Path(uploaded_file.name).name
                    staged_file.write_bytes(uploaded_file.getvalue())
                    report = agent.audit_file(staged_file, progress_callback=_on_progress)
            else:
                report = agent.audit_file(target_path, progress_callback=_on_progress)
            status.update(label="Preparando relatórios para download…")
            downloads = (
                export_report_to_markdown(report),
                export_report_to_json(report),
                export_report_to_pdf(report),
            )
        except Exception as exc:
            status.update(label="A auditoria não pôde ser concluída.", state="error")
            st.error(str(exc))
        else:
            st.session_state["last_run"] = (report, downloads)
            status.update(label="Auditoria concluída", state="complete")

last_run = st.session_state.get("last_run")

if last_run is not None:
    report, (md_str, json_str, pdf_bytes) = last_run
    for warning in report.avisos:
        st.warning(warning)
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
    st.caption(report.gemini_summary)

    # Botões de Exportação
    st.subheader("📥 Exportar Relatório de Diagnóstico")

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
    st.subheader("Referências encontradas")

    statuses = [status.value for status in VerdictStatus]
    status_filter = st.multiselect(
        "Filtrar por veredito",
        options=statuses,
        default=statuses,
    )
    visible_results = [
        result for result in report.resultados if result.status_final.value in status_filter
    ]

    if visible_results:
        st.caption("Clique em uma referência para ver o diagnóstico.")
        selected_statuses = ",".join(status for status in statuses if status in status_filter)
        selection = st.dataframe(
            [
                {
                    "Nº": result.indice,
                    "Referência": result.referencia_extraida.titulo
                    or result.referencia_extraida.texto_original
                    or "Sem título",
                    "Status": result.status_final.value,
                }
                for result in visible_results
            ],
            key=f"referencias:{report.data_hora_iso}:{selected_statuses}",
            hide_index=True,
            use_container_width=True,
            on_select="rerun",
            selection_mode="single-row",
            column_config={
                "Nº": st.column_config.NumberColumn(width="small"),
                "Referência": st.column_config.TextColumn(width="large"),
                "Status": st.column_config.TextColumn(width="medium"),
            },
        ).selection.rows
        if selection and 0 <= selection[0] < len(visible_results):
            res = visible_results[selection[0]]
            ref = res.referencia_extraida
            m = res.metricas
            off = res.melhor_correspondencia_oficial

            st.subheader(f"Referência {res.indice} · {res.status_final.value}")
            st.markdown(f"**Categoria na Taxonomia:** `{res.categoria_taxonomia.value}`")
            st.markdown(f"**Diagnóstico Explicativo:** {res.diagnostico_explicativo}")
            st.markdown(f"**Ação Recomendada:** *{res.acao_recomendada}*")

            if res.falhas_consulta:
                st.caption("Falhas de consulta · " + ", ".join(res.falhas_consulta))
            if res.estado_investigacao:
                st.write(res.estado_investigacao)
            if res.correcao_verificada:
                st.write(res.correcao_verificada.citation)
                st.code(res.correcao_verificada.bibtex, language="bibtex")

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
    elif report.resultados:
        st.info("Nenhuma referência corresponde aos filtros selecionados.")
    else:
        st.info("Nenhuma referência disponível para exibir.")
