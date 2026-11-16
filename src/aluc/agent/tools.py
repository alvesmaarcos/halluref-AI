"""Declarações e handlers das Tools de verificação bibliográfica para o Agente Gemini (RN01–RN05, RF04)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from aluc.clients.crossref import CrossrefClient
from aluc.clients.http_client import PoliteHttpClient
from aluc.clients.openalex import OpenAlexClient
from aluc.clients.semantic_scholar import SemanticScholarClient
from aluc.config import AlucConfig
from aluc.rules.metrics import (
    calculate_title_similarity,
    compute_comparison_metrics,
    evaluate_decision_matrix,
)
from aluc.schemas import (
    ComparisonMetrics,
    OfficialWorkMetadata,
    ParsedReference,
    ToolCallTrace,
)

# Declarações de Tools no formato FunctionParam da Interactions API (google-genai >= 2.30.1)
AGENT_TOOL_DECLARATIONS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "name": "resolve_doi_tool",
        "description": (
            "RN01: Resolve e valida prioritariamente um código DOI nas APIs do Crossref, doi.org e OpenAlex. "
            "Retorna se o DOI existe ou é 404 (DOI Fantasma), os metadados oficiais vinculados ao DOI "
            "e a similaridade textual exata com o título citado para detectar DOI Cruzado (Hijacked)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "doi": {
                    "type": "string",
                    "description": "O identificador DOI extraído da referência (ex: '10.1038/nature14539').",
                }
            },
            "required": ["doi"],
        },
    },
    {
        "type": "function",
        "name": "search_crossref_tool",
        "description": (
            "RF04 (1ª Base em Cascata): Busca a obra pelo título bibliográfico na API do Crossref. "
            "Retorna o melhor candidato encontrado junto com o percentual exato de similaridade de título (RN02), "
            "interseção de sobrenomes dos autores (RN03) e diferença de ano (RN04)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query_title": {
                    "type": "string",
                    "description": "Título da referência a ser buscado no Crossref.",
                }
            },
            "required": ["query_title"],
        },
    },
    {
        "type": "function",
        "name": "search_openalex_tool",
        "description": (
            "RF04 (2ª Base em Cascata - Segunda Opinião): Busca a obra pelo título na API do OpenAlex "
            "quando o Crossref não encontrar correspondência forte (< 85%) ou quando não houver DOI. "
            "Retorna o melhor candidato e as métricas exatas das regras RN02, RN03 e RN04."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query_title": {
                    "type": "string",
                    "description": "Título da referência a ser buscado no OpenAlex.",
                }
            },
            "required": ["query_title"],
        },
    },
    {
        "type": "function",
        "name": "search_semantic_scholar_tool",
        "description": (
            "Seção 1 / Fallback 3: Busca a obra pelo título na API do Semantic Scholar "
            "(excelente cobertura para Ciência da Computação, conferências e preprints arXiv) "
            "caso Crossref e OpenAlex tenham retornado similaridade baixa (< 85%)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query_title": {
                    "type": "string",
                    "description": "Título da referência a ser buscado no Semantic Scholar.",
                }
            },
            "required": ["query_title"],
        },
    },
]


class ReferenceAuditToolkit:
    """Mantém o estado e executa as tools durante a auditoria de uma referência individual."""

    def __init__(
        self,
        reference: ParsedReference,
        crossref: CrossrefClient,
        openalex: OpenAlexClient,
        semantic_scholar: SemanticScholarClient,
    ) -> None:
        self.reference = reference
        self.crossref = crossref
        self.openalex = openalex
        self.semantic_scholar = semantic_scholar

        self.traces: List[ToolCallTrace] = []
        self.doi_resolution_status: str = (
            "NAO_INFORMADO" if not reference.doi else "PENDENTE"
        )
        self.doi_resolved_work: Optional[OfficialWorkMetadata] = None
        self.best_candidate: Optional[OfficialWorkMetadata] = None
        self.best_metrics: ComparisonMetrics = compute_comparison_metrics(
            reference, None, self.doi_resolution_status
        )

    @classmethod
    def create_clients(
        cls, config: Optional[AlucConfig] = None
    ) -> Tuple[PoliteHttpClient, CrossrefClient, OpenAlexClient, SemanticScholarClient]:
        http = PoliteHttpClient(config)
        return (
            http,
            CrossrefClient(http),
            OpenAlexClient(http),
            SemanticScholarClient(http),
        )

    @staticmethod
    def _candidate_rank_key(m: ComparisonMetrics) -> tuple[int, int, float, float]:
        """Chave de ordenação para desempatar candidatos homônimos:
        1. Faixa de similaridade de título (FORTE=2, PARCIAL=1, BAIXA=0)
        2. Nível de interseção de autoria quando título é forte/parcial (ALTA=2, PARCIAL=1, outros=0)
        3. Percentual exato de similaridade de título
        4. Proximidade temporal (negativo da diferença de ano)
        """
        tier_score = (
            2
            if m.similaridade_titulo_pct >= 85.0
            else (1 if m.similaridade_titulo_pct >= 60.0 else 0)
        )
        auth_score = (
            2
            if m.correspondencia_autoria == "ALTA"
            else (1 if m.correspondencia_autoria == "PARCIAL" else 0)
        )
        year_penalty = -float(m.diferenca_ano if m.diferenca_ano is not None else 99)
        return (
            tier_score,
            auth_score if tier_score > 0 else 0,
            m.similaridade_titulo_pct,
            year_penalty,
        )

    def _select_best_candidate(
        self, candidates: List[OfficialWorkMetadata]
    ) -> Tuple[Optional[OfficialWorkMetadata], float]:
        """Seleciona o melhor candidato da API priorizando faixa de título e interseção de autoria."""
        best_item: Optional[OfficialWorkMetadata] = None
        best_rank: tuple[int, int, float, float] = (-1, -1, -1.0, -999.0)
        best_sim: float = 0.0

        for cand in candidates:
            m = compute_comparison_metrics(
                self.reference, cand, self.doi_resolution_status
            )
            rk = self._candidate_rank_key(m)
            if rk > best_rank:
                best_rank = rk
                best_item = cand
                best_sim = m.similaridade_titulo_pct

        return best_item, best_sim

    def _update_best_state(
        self, candidate: Optional[OfficialWorkMetadata]
    ) -> ComparisonMetrics:
        """Atualiza o melhor candidato global da sessão caso supere o candidato anterior."""
        metrics = compute_comparison_metrics(
            self.reference, candidate, self.doi_resolution_status
        )

        # Se o DOI resolvido mostrou DOI Cruzado (Hijacked), preserva essa evidência crítica (RN01 Critério 2)
        if self.doi_resolution_status == "CRUZADO_HIJACKED":
            metrics.doi_status = "CRUZADO_HIJACKED"
            metrics.doi_resolvido = True

        if candidate is not None:
            if self.best_candidate is None or self._candidate_rank_key(
                metrics
            ) > self._candidate_rank_key(self.best_metrics):
                self.best_candidate = candidate
                self.best_metrics = metrics
        else:
            if self.best_candidate is None:
                self.best_metrics = metrics

        return metrics

    def resolve_doi_tool(self, doi: str) -> Dict[str, Any]:
        """Executa RN01: Resolução direta de DOI no Crossref, doi.org e OpenAlex."""
        target_doi = (doi or self.reference.doi or "").strip()
        status, work = self.crossref.resolve_doi(target_doi)

        # Se estiver registrado em outra agência (ex: DataCite / arXiv), tenta resolver via OpenAlex
        if work is None and status == "REGISTRADO_OUTRA_AGENCIA":
            oa_work = self.openalex.resolve_doi(target_doi)
            if oa_work is not None:
                status = "RESOLVIDO"
                work = oa_work

        if status == "RESOLVIDO" and work is not None:
            self.doi_resolved_work = work
            sim = calculate_title_similarity(
                self.reference.titulo, work.titulo_oficial
            )
            if sim < 60.0:
                self.doi_resolution_status = "CRUZADO_HIJACKED"
            else:
                self.doi_resolution_status = "VALIDO_CORRESPONDENTE"
            metrics = self._update_best_state(work)
            verdict, category, action = evaluate_decision_matrix(metrics)

            summary = (
                f"DOI '{target_doi}' resolvido via {work.fonte_api}. "
                f"Título oficial: '{work.titulo_oficial}' (Similaridade: {metrics.similaridade_titulo_pct:.1f}% - {metrics.faixa_similaridade_titulo}). "
                f"Status DOI: {metrics.doi_status}. Autoria: {metrics.correspondencia_autoria}."
            )
            self.traces.append(
                ToolCallTrace(
                    tool_name="resolve_doi_tool",
                    arguments={"doi": target_doi},
                    summary_result=summary,
                    candidates_found=1,
                    best_similarity_pct=metrics.similaridade_titulo_pct,
                )
            )
            return {
                "status": "DOI_RESOLVED",
                "doi_status": metrics.doi_status,
                "official_work": work.model_dump(),
                "metrics": metrics.model_dump(),
                "matrix_recommendation": {
                    "status_final": verdict.value,
                    "categoria_taxonomia": category.value,
                    "acao_recomendada": action,
                },
            }

        # Caso 404 Not Found no Crossref e doi.org (RN01 Critério 1)
        self.doi_resolution_status = "INEXISTENTE_404"
        metrics = self._update_best_state(None)
        verdict, category, action = evaluate_decision_matrix(metrics)
        summary = (
            f"DOI '{target_doi}' retornou 404 Not Found no Crossref e no doi.org (DOI Inexistente - RN01 Critério 1)."
        )
        self.traces.append(
            ToolCallTrace(
                tool_name="resolve_doi_tool",
                arguments={"doi": target_doi},
                summary_result=summary,
                candidates_found=0,
                best_similarity_pct=0.0,
            )
        )
        return {
            "status": "DOI_404_NOT_FOUND",
            "doi_status": "INEXISTENTE_404",
            "message": summary,
            "metrics": metrics.model_dump(),
            "matrix_recommendation": {
                "status_final": verdict.value,
                "categoria_taxonomia": category.value,
                "acao_recomendada": action,
            },
        }

    def _run_title_search_tool(
        self,
        tool_name: str,
        provider_name: str,
        query_title: str,
        candidates: List[OfficialWorkMetadata],
    ) -> Dict[str, Any]:
        best_cand, best_sim = self._select_best_candidate(candidates)
        metrics = self._update_best_state(best_cand)
        effective_metrics = self.best_metrics
        verdict, category, action = evaluate_decision_matrix(effective_metrics)

        if best_cand is not None:
            summary = (
                f"{provider_name}: {len(candidates)} resultado(s). Melhor: '{best_cand.titulo_oficial}' "
                f"(Similaridade: {metrics.similaridade_titulo_pct:.1f}% [{metrics.faixa_similaridade_titulo}], "
                f"Autoria: {metrics.correspondencia_autoria}, Ano oficial: {best_cand.ano_oficial})."
            )
        else:
            summary = f"{provider_name}: Nenhum resultado retornado para '{query_title}'."

        self.traces.append(
            ToolCallTrace(
                tool_name=tool_name,
                arguments={"query_title": query_title},
                summary_result=summary,
                candidates_found=len(candidates),
                best_similarity_pct=best_sim,
            )
        )

        return {
            "provider": provider_name,
            "candidates_count": len(candidates),
            "best_candidate_in_provider": (
                best_cand.model_dump() if best_cand else None
            ),
            "provider_metrics": metrics.model_dump(),
            "overall_best_metrics": effective_metrics.model_dump(),
            "matrix_recommendation": {
                "status_final": verdict.value,
                "categoria_taxonomia": category.value,
                "acao_recomendada": action,
            },
        }

    def search_crossref_tool(self, query_title: str) -> Dict[str, Any]:
        """Executa RF04 (1ª base): Busca bibliográfica por título no Crossref."""
        q = (query_title or self.reference.titulo).strip()
        first_surname = (
            self.best_metrics.sobrenomes_citados[0]
            if self.best_metrics.sobrenomes_citados
            else None
        )
        try:
            candidates = self.crossref.search_by_title(
                q, rows=5, first_author_surname=first_surname
            )
        except TypeError:
            candidates = self.crossref.search_by_title(q, rows=5)
        return self._run_title_search_tool(
            "search_crossref_tool", "Crossref", q, candidates
        )

    def search_openalex_tool(self, query_title: str) -> Dict[str, Any]:
        """Executa RF04 (2ª base): Busca por título no OpenAlex."""
        q = (query_title or self.reference.titulo).strip()
        candidates = self.openalex.search_by_title(q, per_page=5)
        return self._run_title_search_tool(
            "search_openalex_tool", "OpenAlex", q, candidates
        )

    def search_semantic_scholar_tool(self, query_title: str) -> Dict[str, Any]:
        """Executa Fallback 3 (Seção 1): Busca por título no Semantic Scholar."""
        q = (query_title or self.reference.titulo).strip()
        candidates = self.semantic_scholar.search_by_title(q, limit=5)
        return self._run_title_search_tool(
            "search_semantic_scholar_tool", "Semantic Scholar", q, candidates
        )

    def execute_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Despacha a chamada de função solicitada pelo modelo Gemini."""
        if name == "resolve_doi_tool":
            return self.resolve_doi_tool(str(arguments.get("doi", self.reference.doi or "")))
        if name == "search_crossref_tool":
            return self.search_crossref_tool(
                str(arguments.get("query_title", self.reference.titulo))
            )
        if name == "search_openalex_tool":
            return self.search_openalex_tool(
                str(arguments.get("query_title", self.reference.titulo))
            )
        if name == "search_semantic_scholar_tool":
            return self.search_semantic_scholar_tool(
                str(arguments.get("query_title", self.reference.titulo))
            )
        return {"error": f"Tool desconhecida: {name}"}
