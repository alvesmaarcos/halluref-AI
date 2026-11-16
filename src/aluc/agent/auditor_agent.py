"""Agente Auditor de Referências Bibliográficas com Tool-Calling via Gemini 3.8 Flash (RF04, RF05, RNF03)."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from google import genai

from aluc.agent.parser_agent import SemanticReferenceParser
from aluc.agent.tools import AGENT_TOOL_DECLARATIONS, ReferenceAuditToolkit
from aluc.clients.crossref import CrossrefClient
from aluc.clients.http_client import PoliteHttpClient
from aluc.clients.openalex import OpenAlexClient
from aluc.clients.semantic_scholar import SemanticScholarClient
from aluc.config import AlucConfig
from aluc.ingestion import extract_references_from_file
from aluc.rules.metrics import evaluate_decision_matrix
from aluc.schemas import (
    AuditReport,
    ComparisonMetrics,
    HallucinationCategory,
    OfficialWorkMetadata,
    ParsedReference,
    ReferenceAuditResult,
    VerdictStatus,
)

AUDITOR_SYSTEM_INSTRUCTION = """Você é um Agente de IA Auditor de Referências Bibliográficas (Versão 1.0).
Sua missão é verificar a veracidade de cada citação acadêmica consultando obrigatoriamente as tools científicas
em cascata e aplicando as Regras de Negócio (RN01 a RN05) e a Matriz de Decisão.

FLUXO OBRIGATÓRIO DE CHAMADA DE TOOLS (RF04 e RN01):
1. Se a referência possuir um `doi` preenchido, chame PRIMEIRO `resolve_doi_tool(doi=...)` (RN01).
   - Se o DOI resolver e a similaridade do título for < 60%, trata-se de DOI Cruzado (Hijacked) -> ALUCINADA.
   - Se o DOI retornar 404 (DOI Inexistente), chame também as tools de busca por título para verificar se a obra existe sem aquele DOI.
2. Caso não haja DOI ou o DOI não confirme a obra com similaridade >= 85%, consulte por título em cascata:
   - Passo A: Chame `search_crossref_tool(query_title=...)`.
   - Passo B: Se a melhor similaridade no Crossref for < 85%, chame `search_openalex_tool(query_title=...)`.
   - Passo C: Se a melhor similaridade no OpenAlex ainda for < 85%, chame `search_semantic_scholar_tool(query_title=...)`.
3. Nunca julgue uma referência de memória sem invocar as tools.

REGRAS DE JULGAMENTO (RN01 a RN05 e Matriz de Decisão):
- VÁLIDA: Similaridade de título >= 85% E correspondência de autoria ALTA (1º autor coincide + >=50% dos demais) E (DOI válido correspondente ou ausente) E diferença de ano <= 2 anos.
- SUSPEITA (Revisar):
  * Título entre 60% e 84.99% com autores compatíveis.
  * Título >= 85%, mas diferença de ano > 2 anos (RN04) ou correspondência de autoria apenas PARCIAL.
  * Obra não encontrada nas APIs (< 60%), mas classificada como exceção de escopo RN05 (`excecao_escopo_rn05=True`: normas ISO/ABNT, legislação, sites/@misc/URL, monografias ou livros locais).
- ALUCINADA:
  * Caso 1 (Fantasma / Ghost Reference): Similaridade de título < 60% em todas as bases consultadas (e não é exceção RN05).
  * Caso 2 (Quimera / Atribuição Falsa): Título encontrado (>= 60%), mas 0% de interseção nos sobrenomes dos autores (`SEM_INTERSECAO`).
  * Caso 3 (DOI Falso/Trocado): DOI aponta para outro artigo sem relação (similaridade < 60% -> DOI Cruzado) ou DOI retorna 404 com título também ausente (< 60%).

Ao concluir as consultas nas tools, responda APENAS com um objeto JSON contendo:
- `status_final`: "VÁLIDA" | "SUSPEITA (Revisar)" | "ALUCINADA"
- `categoria_taxonomia`: uma das categorias oficiais da taxonomia
- `diagnostico_explicativo`: justificativa clara, objetiva e explicativa em português (RF05), citando os autores, anos, DOIs e percentuais encontrados nas bases oficiais vs. os citados no documento.
- `acao_recomendada`: orientação prática ao autor do manuscrito.
"""

FINAL_JUDGMENT_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "status_final": {
            "type": "string",
            "enum": [s.value for s in VerdictStatus],
        },
        "categoria_taxonomia": {
            "type": "string",
            "enum": [c.value for c in HallucinationCategory],
        },
        "diagnostico_explicativo": {"type": "string"},
        "acao_recomendada": {"type": "string"},
    },
    "required": [
        "status_final",
        "categoria_taxonomia",
        "diagnostico_explicativo",
        "acao_recomendada",
    ],
}


def build_deterministic_explanation(
    ref: ParsedReference,
    official: Optional[OfficialWorkMetadata],
    metrics: ComparisonMetrics,
    verdict: VerdictStatus,
    category: HallucinationCategory,
) -> str:
    """Constrói um diagnóstico explicativo detalhado (RF05) baseado nas evidências coletadas pelas tools."""
    cited_authors_str = ", ".join(ref.autores) if ref.autores else "Não informados"
    cited_year_str = str(ref.ano) if ref.ano else "s/d"

    if category == HallucinationCategory.DOI_HIJACKING and official is not None:
        off_authors = ", ".join(official.autores_oficiais[:4]) or "Não informados"
        return (
            f"Sequestro de DOI (DOI Cruzado - RN01 Critério 2): O DOI informado ({ref.doi}) é válido na base "
            f"{official.fonte_api}, porém pertence a uma obra completamente diferente: "
            f"'{official.titulo_oficial}' ({off_authors}, {official.ano_oficial}). "
            f"A similaridade entre o título citado ('{ref.titulo}') e o título oficial vinculado ao DOI é de apenas "
            f"{metrics.similaridade_titulo_pct:.1f}% (< 60%)."
        )

    if category == HallucinationCategory.DOI_FABRICATION:
        if (
            metrics.similaridade_titulo_pct < 85.0
            or metrics.correspondencia_autoria == "SEM_INTERSECAO"
        ):
            return (
                f"Invenção de DOI e Obra Fantasma (RN01 Critério 1): O DOI citado ({ref.doi}) retornou erro "
                f"'404 Not Found' nas APIs do Crossref e do doi.org (não está registrado em nenhuma agência), "
                f"e a busca textual pelo título '{ref.titulo}' também não encontrou correspondência válida "
                f"com autoria compatível (melhor similaridade bruta: {metrics.similaridade_titulo_pct:.1f}%)."
            )
        off_authors = (
            ", ".join(official.autores_oficiais[:4]) if official else "Autores oficiais"
        )
        return (
            f"DOI Inexistente (RN01 Critério 1): A obra '{ref.titulo}' foi localizada por busca textual "
            f"({off_authors}, {official.ano_oficial if official else 's/d'}), porém o DOI informado no texto "
            f"({ref.doi}) retorna '404 Not Found' no Crossref e doi.org."
        )

    if category == HallucinationCategory.UNVERIFIABLE_GREY_LITERATURE:
        return (
            f"Exceção de Escopo (RN05 — {metrics.motivo_rn05}): A referência '{ref.titulo}' não foi localizada "
            f"nas APIs indexadas de artigos científicos (Crossref, OpenAlex e Semantic Scholar), mas apresenta "
            f"características de literatura cinzenta, norma técnica, legislação, livro local ou página web. "
            f"Classificada como Não Verificável Automaticamente para revisão manual."
        )

    if category == HallucinationCategory.GHOST_REFERENCE:
        return (
            f"Invenção Total (Ghost Reference — RN02): Após consulta em cascata no Crossref, OpenAlex e "
            f"Semantic Scholar, nenhuma obra publicada corresponde ao título '{ref.titulo}' "
            f"(melhor similaridade encontrada: {metrics.similaridade_titulo_pct:.1f}%, inferior ao limiar mínimo de 60%). "
            f"Padrão típico de referência fabricada por modelo de linguagem."
        )

    if category == HallucinationCategory.CHIMERA and official is not None:
        off_authors = ", ".join(official.autores_oficiais) or "Não informados"
        return (
            f"Referência Quimera / Atribuição Falsa de Autoria (RN03): O título '{official.titulo_oficial}' "
            f"existe na base {official.fonte_api} (similaridade de {metrics.similaridade_titulo_pct:.1f}%), "
            f"mas pertence aos autores [{off_authors}] ({official.ano_oficial}), e não aos autores "
            f"[{cited_authors_str}] ({cited_year_str}) citados no documento (0% de interseção nos sobrenomes)."
        )

    if category == HallucinationCategory.VENUE_OR_YEAR_DISTORTION and official is not None:
        return (
            f"Distorção Temporal (RN04): O artigo '{official.titulo_oficial}' e seus autores coincidem com o "
            f"registro oficial na base {official.fonte_api} (similaridade de {metrics.similaridade_titulo_pct:.1f}%), "
            f"porém o ano citado no documento ({cited_year_str}) diverge em {metrics.diferenca_ano} anos do ano oficial "
            f"de publicação ({official.ano_oficial}), excedendo a tolerância máxima de 2 anos."
        )

    if category == HallucinationCategory.PARTIAL_TITLE_OR_METADATA and official is not None:
        off_authors = ", ".join(official.autores_oficiais[:4]) or "Não informados"
        if metrics.faixa_similaridade_titulo == "PARCIAL":
            return (
                f"Correspondência Parcial de Título (RN02): Foi encontrada a obra '{official.titulo_oficial}' "
                f"({off_authors}, {official.ano_oficial}) na base {official.fonte_api} com similaridade de "
                f"{metrics.similaridade_titulo_pct:.1f}% (faixa entre 60% e 84%). Recomenda-se revisar se houve "
                f"truncamento de subtítulo ou erro de extração."
            )
        return (
            f"Correspondência Parcial de Autoria (RN03): O título '{official.titulo_oficial}' foi confirmado "
            f"({metrics.similaridade_titulo_pct:.1f}% na base {official.fonte_api}), mas a lista de autores citada "
            f"[{cited_authors_str}] apresenta correspondência apenas parcial com a autoria oficial [{off_authors}] "
            f"(primeiro autor coincide: {'Sim' if metrics.primeiro_autor_coincide else 'Não'}; "
            f"interseção dos demais: {metrics.intersecao_demais_autores_pct:.0f}%)."
        )

    if verdict == VerdictStatus.VALIDA and official is not None:
        off_authors = ", ".join(official.autores_oficiais[:4])
        if len(official.autores_oficiais) > 4:
            off_authors += " et al."
        year_note = (
            f"diferença temporal de {metrics.diferenca_ano} ano(s) dentro da tolerância RN04"
            if (metrics.diferenca_ano or 0) > 0
            else "ano exato confirmado"
        )
        return (
            f"Referência íntegra validada na base {official.fonte_api}: '{official.titulo_oficial}' "
            f"({off_authors}, {official.ano_oficial}). Similaridade de título: {metrics.similaridade_titulo_pct:.1f}% "
            f"(>= 85%), correspondência de autoria ALTA e {year_note}."
        )

    return "Auditoria concluída conforme regras RN01 a RN05."


class BibliographicAuditorAgent:
    """Orquestrador principal do Agente de Auditoria com Tool-Calling no Gemini 3.8 Flash."""

    def __init__(
        self,
        config: Optional[AlucConfig] = None,
        http_client: Optional[PoliteHttpClient] = None,
        crossref: Optional[CrossrefClient] = None,
        openalex: Optional[OpenAlexClient] = None,
        semantic_scholar: Optional[SemanticScholarClient] = None,
    ) -> None:
        self.config = config or AlucConfig.from_env()
        self.http_client = http_client or PoliteHttpClient(self.config)
        self.crossref = crossref or CrossrefClient(self.http_client)
        self.openalex = openalex or OpenAlexClient(self.http_client)
        self.semantic_scholar = semantic_scholar or SemanticScholarClient(
            self.http_client
        )
        self.parser = SemanticReferenceParser(self.config)

        self.genai_client: Optional[genai.Client] = None
        if self.config.gemini_api_key:
            self.genai_client = genai.Client(api_key=self.config.gemini_api_key)

    def _ensure_cascade_executed(self, toolkit: ReferenceAuditToolkit) -> None:
        """Garante que o protocolo de busca encadeada (RN01 e RF04) foi cumprido integralmente
        caso o LLM tenha encerrado prematuramente ou quando executado sem chave de API.
        """
        called_names = {t.tool_name for t in toolkit.traces}

        # 1. RN01: Se houver DOI e resolve_doi_tool ainda não foi chamada
        if toolkit.reference.doi and "resolve_doi_tool" not in called_names:
            toolkit.resolve_doi_tool(toolkit.reference.doi)
            called_names.add("resolve_doi_tool")

        # Se o DOI já caracterizou DOI Cruzado (Hijacked), não sobrescreve com busca textual
        if toolkit.doi_resolution_status == "CRUZADO_HIJACKED":
            return

        # 2. RF04: Se ainda não encontrou correspondência forte (>= 85%) com autoria ALTA, segue a cascata
        def _needs_more_search() -> bool:
            if not toolkit.reference.titulo:
                return False
            if (
                toolkit.best_metrics.similaridade_titulo_pct >= 85.0
                and toolkit.best_metrics.correspondencia_autoria == "ALTA"
            ):
                return False
            return True

        if _needs_more_search() and "search_crossref_tool" not in called_names:
            toolkit.search_crossref_tool(toolkit.reference.titulo)
            called_names.add("search_crossref_tool")

        if _needs_more_search() and "search_openalex_tool" not in called_names:
            toolkit.search_openalex_tool(toolkit.reference.titulo)
            called_names.add("search_openalex_tool")

        if _needs_more_search() and "search_semantic_scholar_tool" not in called_names:
            toolkit.search_semantic_scholar_tool(toolkit.reference.titulo)
            called_names.add("search_semantic_scholar_tool")

    def audit_single_reference(
        self, index: int, ref: ParsedReference
    ) -> ReferenceAuditResult:
        """Audita uma única referência utilizando o ciclo de Tool-Calling do Gemini 3.8 Flash."""
        toolkit = ReferenceAuditToolkit(
            reference=ref,
            crossref=self.crossref,
            openalex=self.openalex,
            semantic_scholar=self.semantic_scholar,
        )

        llm_diagnosis: Optional[str] = None
        llm_status: Optional[VerdictStatus] = None
        llm_category: Optional[HallucinationCategory] = None
        llm_action: Optional[str] = None

        if self.genai_client is not None:
            try:
                user_prompt = (
                    "Audite a seguinte referência bibliográfica invocando as tools necessárias "
                    "(inicie por `resolve_doi_tool` se houver DOI, depois use a cascata "
                    "`search_crossref_tool` -> `search_openalex_tool` -> `search_semantic_scholar_tool`):\n\n"
                    f"{json.dumps(ref.model_dump(), ensure_ascii=False, indent=2)}"
                )
                interaction = self.genai_client.interactions.create(
                    model=self.config.gemini_model,
                    system_instruction=AUDITOR_SYSTEM_INSTRUCTION,
                    input=user_prompt,
                    tools=AGENT_TOOL_DECLARATIONS,
                    generation_config={
                        "seed": self.config.seed,
                        "thinking_level": self.config.thinking_level,
                    },
                )

                # Loop de Tool-Calling (máximo de 6 turnos de ferramentas por referência)
                for _ in range(6):
                    steps = interaction.steps or []
                    function_calls = [
                        s for s in steps if getattr(s, "type", None) == "function_call"
                    ]
                    if not function_calls:
                        break

                    function_results: List[Dict[str, Any]] = []
                    for fc in function_calls:
                        tool_output = toolkit.execute_tool(
                            fc.name, dict(fc.arguments or {})
                        )
                        function_results.append(
                            {
                                "type": "function_result",
                                "call_id": fc.id,
                                "name": fc.name,
                                "result": json.dumps(tool_output, ensure_ascii=False),
                            }
                        )

                    interaction = self.genai_client.interactions.create(
                        model=self.config.gemini_model,
                        previous_interaction_id=interaction.id,
                        system_instruction=AUDITOR_SYSTEM_INSTRUCTION,
                        input=function_results,
                        tools=AGENT_TOOL_DECLARATIONS,
                        generation_config={
                            "seed": self.config.seed,
                            "thinking_level": self.config.thinking_level,
                        },
                    )

                # Garante que todas as etapas obrigatórias da cascata foram executadas
                self._ensure_cascade_executed(toolkit)

                # Solicita ou extrai o julgamento estruturado final
                raw_text = (interaction.output_text or "").strip()
                if not raw_text.startswith("{"):
                    summary_input = (
                        "Com base nas evidências e métricas exatas retornadas pelas tools: "
                        f"{json.dumps(toolkit.best_metrics.model_dump(), ensure_ascii=False)}, "
                        "gere o veredito final estruturado em JSON."
                    )
                    final_interaction = self.genai_client.interactions.create(
                        model=self.config.gemini_model,
                        previous_interaction_id=interaction.id,
                        system_instruction=AUDITOR_SYSTEM_INSTRUCTION,
                        input=summary_input,
                        response_format=FINAL_JUDGMENT_JSON_SCHEMA,
                        response_mime_type="application/json",
                        generation_config={
                            "seed": self.config.seed,
                            "thinking_level": self.config.thinking_level,
                        },
                    )
                    raw_text = (final_interaction.output_text or "").strip()

                parsed_judgment = json.loads(raw_text)
                llm_status = VerdictStatus(parsed_judgment["status_final"])
                llm_category = HallucinationCategory(
                    parsed_judgment["categoria_taxonomia"]
                )
                llm_diagnosis = parsed_judgment.get("diagnostico_explicativo", "").strip()
                llm_action = parsed_judgment.get("acao_recomendada", "").strip()
            except Exception:
                # Continua de forma resiliente garantindo execução completa das tools e Matriz de Decisão
                pass

        # Garante que o protocolo em cascata foi cumprido mesmo em modo sem chave ou fallback
        self._ensure_cascade_executed(toolkit)

        # Avalia a Matriz de Decisão oficial (Seção 4) sobre as melhores métricas obtidas pelas tools
        matrix_verdict, matrix_category, matrix_action = evaluate_decision_matrix(
            toolkit.best_metrics
        )

        # O status final e a categoria respeitam estritamente os limiares matemáticos da Matriz de Decisão (RNF03),
        # combinando com a justificativa explicativa gerada pelo Agente (RF05).
        final_status = matrix_verdict
        final_category = matrix_category
        final_action = llm_action if (llm_action and llm_status == matrix_verdict) else matrix_action

        if llm_diagnosis and llm_status == matrix_verdict:
            final_diagnosis = llm_diagnosis
        else:
            final_diagnosis = build_deterministic_explanation(
                ref=ref,
                official=toolkit.best_candidate or toolkit.doi_resolved_work,
                metrics=toolkit.best_metrics,
                verdict=final_status,
                category=final_category,
            )

        return ReferenceAuditResult(
            indice=index,
            referencia_extraida=ref,
            status_final=final_status,
            categoria_taxonomia=final_category,
            diagnostico_explicativo=final_diagnosis,
            acao_recomendada=final_action,
            melhor_correspondencia_oficial=(
                toolkit.best_candidate or toolkit.doi_resolved_work
            ),
            metricas=toolkit.best_metrics,
            rastro_tools=toolkit.traces,
        )

    def audit_file(
        self,
        file_path: str | Path,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> AuditReport:
        """Executa o fluxo completo (RF01 -> RF06):
        1. Isola a seção de referências do arquivo (.pdf, .bib, .tex) respeitando RNF02.
        2. Estrutura cada referência em JSON via Parser Semântico (RF03).
        3. Audita cada referência via Tool-Calling (RN01–RN05, RF04, RF05).
        4. Consolida o relatório final (RF06).
        """
        path = Path(file_path)
        source_format, isolated_block = extract_references_from_file(path)

        parsed_refs = self.parser.parse_references(
            isolated_block, source_format=source_format
        )

        results: List[ReferenceAuditResult] = []
        total = len(parsed_refs)

        for idx, ref in enumerate(parsed_refs, start=1):
            if progress_callback:
                progress_callback(
                    idx,
                    total,
                    f"Auditando referência [{idx}/{total}]: {ref.titulo[:65]}...",
                )
            result = self.audit_single_reference(idx, ref)
            results.append(result)

        preview = isolated_block[:1500] + (
            "\n... [truncado na visualização]" if len(isolated_block) > 1500 else ""
        )

        report = AuditReport(
            arquivo_origem=path.name,
            formato_origem=source_format,
            data_hora_iso=datetime.now(timezone.utc).isoformat(),
            secao_referencias_isolada_preview=preview,
            resultados=results,
        )
        report.recompute_totals()
        return report
