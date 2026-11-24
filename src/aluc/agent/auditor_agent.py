"""Auditoria bibliográfica local e investigação opcional em lote."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List, Optional
from google import genai

from aluc.agent.investigation import investigate_references
from aluc.agent.parser_agent import SemanticReferenceParser, expected_numbered_references
from aluc.agent.tools import ReferenceAuditToolkit
from aluc.clients.crossref import CrossrefClient
from aluc.clients.http_client import PoliteHttpClient, observe_requests
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
    """Orquestra a extração, a auditoria e a investigação bibliográfica."""

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
            self.genai_client = genai.Client(
                api_key=self.config.gemini_api_key,
                http_options=genai.types.HttpOptions(
                    timeout=30000,
                    retry_options=genai.types.HttpRetryOptions(attempts=1),
                ),
            )

    def _ensure_cascade_executed(self, toolkit: ReferenceAuditToolkit, notify: Callable[[str], None]) -> None:
        if toolkit.reference.doi:
            notify("Resolvendo DOI no Crossref…")
            toolkit.resolve_doi_tool(toolkit.reference.doi)

        if toolkit.doi_resolution_status == "CRUZADO_HIJACKED":
            return

        # RF04: Se ainda não encontrou correspondência forte (>= 85%) com autoria ALTA, segue a cascata
        def _needs_more_search() -> bool:
            if not toolkit.reference.titulo:
                return False
            if (
                toolkit.best_metrics.similaridade_titulo_pct >= 85.0
                and toolkit.best_metrics.correspondencia_autoria == "ALTA"
            ):
                return False
            return True

        if _needs_more_search():
            notify("Buscando pelo título em Crossref…")
            toolkit.search_crossref_tool(toolkit.reference.titulo)

        if _needs_more_search():
            notify("Buscando pelo título em OpenAlex…")
            toolkit.search_openalex_tool(toolkit.reference.titulo)

        if _needs_more_search():
            notify("Buscando pelo título em Semantic Scholar…")
            toolkit.search_semantic_scholar_tool(toolkit.reference.titulo)

    def audit_single_reference(
        self, index: int, ref: ParsedReference,
        notify: Callable[[str], None] = lambda _: None,
        *, from_pdf: bool = False,
    ) -> ReferenceAuditResult:
        """Audita uma referência consultando as bases acadêmicas e aplicando a matriz."""
        toolkit = ReferenceAuditToolkit(
            reference=ref,
            crossref=self.crossref,
            openalex=self.openalex,
            semantic_scholar=self.semantic_scholar,
        )

        failed_hosts: set[str] = set()

        def observe(host: str, status: int | None) -> None:
            if status is None:
                notify(f"Aguardando resposta de {host}…")
            elif status >= 400:
                failed_hosts.add(host)
                notify(f"Consulta a {host} falhou (HTTP {status}). Prosseguindo com as evidências disponíveis.")

        with observe_requests(observe):
            self._ensure_cascade_executed(toolkit, notify)

        metrics = toolkit.best_metrics
        official = toolkit.best_candidate or toolkit.doi_resolved_work
        recovered_ocr = False
        if (
            metrics.doi_status == "INEXISTENTE_404"
            and official and official.doi_oficial and ref.doi
            and metrics.similaridade_titulo_pct >= 98
            and metrics.correspondencia_autoria == "ALTA"
        ):
            cited_doi = ref.doi.strip().lower()
            official_doi = official.doi_oficial.strip().lower()
            if from_pdf and metrics.diferenca_ano == 0 and len(cited_doi) == len(official_doi):
                differences = [
                    (left, right) for left, right in zip(cited_doi, official_doi) if left != right
                ]
                recovered_ocr = (
                    cited_doi.partition("/")[0] == official_doi.partition("/")[0]
                    and len(differences) == 1
                    and differences[0] in {("1", "i"), ("1", "l"), ("0", "o")}
                )
            if cited_doi == official_doi or recovered_ocr:
                metrics = metrics.model_copy(update={
                    "doi_status": "VALIDO_CORRESPONDENTE",
                    "doi_resolvido": True,
                })

        verdict, category, action = evaluate_decision_matrix(metrics)
        diagnosis = build_deterministic_explanation(ref, official, metrics, verdict, category)
        if recovered_ocr:
            diagnosis += (
                f" O DOI extraído do PDF ({ref.doi}) difere do DOI cadastrado "
                f"({official.doi_oficial}) por um caractere visualmente semelhante. "
                "O registro oficial confirmou título, autoria e ano."
            )
            action = "Use o DOI cadastrado ao copiar a referência do PDF."
        if failed_hosts and category in {
            HallucinationCategory.GHOST_REFERENCE, HallucinationCategory.DOI_FABRICATION
        }:
            verdict = VerdictStatus.SUSPEITA
            category = HallucinationCategory.CONSULTA_INCONCLUSIVA
            diagnosis = "A consulta ficou incompleta. Serviços com falha: " + ", ".join(sorted(failed_hosts))
            action = "Repita a auditoria ou verifique a referência manualmente."

        return ReferenceAuditResult(
            indice=index,
            referencia_extraida=ref,
            status_final=verdict,
            categoria_taxonomia=category,
            diagnostico_explicativo=diagnosis,
            acao_recomendada=action,
            melhor_correspondencia_oficial=official,
            metricas=metrics,
            rastro_tools=toolkit.traces,
            falhas_consulta=sorted(failed_hosts),
        )

    def audit_file(
        self,
        file_path: str | Path,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> AuditReport:
        """Executa o fluxo completo (RF01 -> RF06):
        1. Isola a seção de referências do arquivo (.pdf, .bib, .tex) respeitando RNF02.
        2. Estrutura as referências localmente, com auxílio opcional do Gemini.
        3. Audita em Python e investiga casos ambíguos em lote.
        4. Consolida o relatório final (RF06).
        """
        def progress(message: str, current: int = 0, total: int = 0) -> None:
            if progress_callback:
                progress_callback(current, total, message)

        path = Path(file_path)
        progress("Lendo o arquivo e localizando a bibliografia…")
        source_format, isolated_block = extract_references_from_file(path, notify=progress)
        warnings = []
        if not isolated_block.strip():
            warnings.append("Bibliografia não localizada. Forneça um arquivo .bib com as referências.")
        extraction_calls = 0

        def parsing_progress(message: str) -> None:
            nonlocal extraction_calls
            extraction_calls += 1
            progress(message)

        progress("Estruturando referências localmente…")
        parsed_refs = self.parser.parse_references(
            isolated_block,
            source_format=source_format,
            before_gemini=parsing_progress,
            notify=progress,
        )
        if isolated_block.strip() and not parsed_refs:
            warnings.append("Nenhuma referência pôde ser estruturada. Confira a bibliografia ou forneça um .bib.")

        if source_format == "PDF":
            expected = expected_numbered_references(isolated_block)
            if parsed_refs and expected and len(parsed_refs) < expected:
                warnings.append(
                    f"Bibliografia localizada. Foram separadas {len(parsed_refs)} de até "
                    f"{expected} referências numeradas. Alguns itens podem ter sido combinados."
                )

        results: List[ReferenceAuditResult] = []
        total = len(parsed_refs)
        for idx, ref in enumerate(parsed_refs, start=1):
            def reference_progress(message: str) -> None:
                progress(f"Referência {idx}/{total} · {message}", idx, total)

            reference_progress(f"Auditando {ref.titulo[:65] or 'referência sem título'}…")
            results.append(self.audit_single_reference(
                idx, ref, reference_progress, from_pdf=source_format == "PDF"
            ))

        investigation_calls = investigate_references(
            results, self.genai_client, self.config,
            {"Crossref": self.crossref, "OpenAlex": self.openalex,
             "Semantic Scholar": self.semantic_scholar},
            progress,
        )
        progress("Consolidando o relatório…")
        preview = isolated_block[:1500] + (
            "\n... [truncado na visualização]" if len(isolated_block) > 1500 else ""
        )

        report = AuditReport(
            arquivo_origem=path.name,
            formato_origem=source_format,
            data_hora_iso=datetime.now(timezone.utc).isoformat(),
            secao_referencias_isolada_preview=preview,
            resultados=results,
            chamadas_gemini_extracao=extraction_calls,
            chamadas_gemini_investigacao=investigation_calls,
            avisos=warnings,
        )
        report.recompute_totals()
        return report
