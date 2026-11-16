"""Modelos de dados Pydantic para estruturação (RF03), regras de negócio (RN01–RN05) e relatórios (RF05, RF06)."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ReferenceType(str, Enum):
    """Tipos de obra para distinção entre artigos indexados e exceções de escopo (RN05)."""

    ARTICLE = "article"
    CONFERENCE = "conference"
    PREPRINT = "preprint"
    BOOK = "book"
    THESIS = "thesis"
    STANDARD = "standard"        # Normas técnicas ISO, ABNT, IEEE (RN05)
    LEGISLATION = "legislation"  # Leis, decretos, portarias (RN05)
    WEBPAGE = "webpage"          # Páginas web / @misc / URLs (RN05)
    TECHREPORT = "techreport"    # Relatórios técnicos locais (RN05)
    OTHER = "other"


class ParsedReference(BaseModel):
    """Objeto JSON padronizado exigido pelo RF03 (Parser Semântico)."""

    texto_original: str = Field(
        description="Trecho bruto original da referência extraída do documento."
    )
    titulo: str = Field(
        default="",
        description="Título principal da obra citada.",
    )
    autores: List[str] = Field(
        default_factory=list,
        description="Lista de nomes dos autores citados na referência.",
    )
    ano: Optional[int] = Field(
        default=None,
        description="Ano de publicação citado (inteiro de 4 dígitos, se presente).",
    )
    veiculo: Optional[str] = Field(
        default=None,
        description="Periódico (journal), conferência, editora ou instituição citada.",
    )
    doi: Optional[str] = Field(
        default=None,
        description="Identificador DOI normalizado (ex: 10.xxxx/yyyy), se presente.",
    )
    url: Optional[str] = Field(
        default=None,
        description="URL ou link externo citado na referência, se presente.",
    )
    tipo_inferido: ReferenceType = Field(
        default=ReferenceType.ARTICLE,
        description="Tipo documental inferido para avaliação de escopo (RN05).",
    )


class ParsedReferenceList(BaseModel):
    """Envelope para extração em lote de referências via Structured Output (RF03)."""

    referencias: List[ParsedReference] = Field(default_factory=list)


class VerdictStatus(str, Enum):
    """Status final da Matriz de Decisão (Seção 4)."""

    VALIDA = "VÁLIDA"
    SUSPEITA = "SUSPEITA (Revisar)"
    ALUCINADA = "ALUCINADA"


class HallucinationCategory(str, Enum):
    """Taxonomia de Alucinações Bibliográficas (Seção 2 e RN05)."""

    NONE = "Nenhuma (Referência Íntegra)"
    GHOST_REFERENCE = "Invenção Total (Ghost Reference)"
    CHIMERA = "Referência Quimera (Mosaico de Metadados)"
    DOI_FABRICATION = "Invenção de DOI (DOI Inexistente / 404)"
    DOI_HIJACKING = "Sequestro de DOI (DOI Cruzado / Hijacked)"
    VENUE_OR_YEAR_DISTORTION = "Distorção de Veículo ou Ano"
    FALSE_AUTHORSHIP = "Atribuição Falsa de Autoria"
    PARTIAL_TITLE_OR_METADATA = "Divergência Parcial de Título ou Autoria (Revisão Manual)"
    UNVERIFIABLE_GREY_LITERATURE = "Não Verificável Automaticamente (Revisão Manual - RN05)"


class OfficialWorkMetadata(BaseModel):
    """Metadados oficiais retornados pelas APIs científicas (Crossref, OpenAlex, Semantic Scholar)."""

    fonte_api: str = Field(description="Nome da base que retornou o registro (Crossref, OpenAlex, Semantic Scholar).")
    titulo_oficial: str = Field(default="")
    autores_oficiais: List[str] = Field(default_factory=list)
    ano_oficial: Optional[int] = None
    veiculo_oficial: Optional[str] = None
    doi_oficial: Optional[str] = None
    url_oficial: Optional[str] = None
    tipo_oficial: Optional[str] = None


class ComparisonMetrics(BaseModel):
    """Métricas determinísticas calculadas para as Regras de Negócio RN01 a RN05."""

    doi_informado: Optional[str] = None
    doi_resolvido: bool = False
    doi_status: str = "NAO_INFORMADO"  # NAO_INFORMADO | VALIDO_CORRESPONDENTE | INEXISTENTE_404 | CRUZADO_HIJACKED
    similaridade_titulo_pct: float = 0.0
    faixa_similaridade_titulo: str = "NAO_ENCONTRADO"  # FORTE (>=85%) | PARCIAL (60-84%) | BAIXA (<60%)
    correspondencia_autoria: str = "SEM_INTERSECAO"    # ALTA | PARCIAL | SEM_INTERSECAO | NAO_AVALIADO
    primeiro_autor_coincide: bool = False
    intersecao_demais_autores_pct: float = 0.0
    sobrenomes_citados: List[str] = Field(default_factory=list)
    sobrenomes_oficiais: List[str] = Field(default_factory=list)
    sobrenomes_em_comum: List[str] = Field(default_factory=list)
    diferenca_ano: Optional[int] = None
    ano_aceitavel: Optional[bool] = None
    excecao_escopo_rn05: bool = False
    motivo_rn05: Optional[str] = None


class ToolCallTrace(BaseModel):
    """Registro de uma chamada de ferramenta (tool) realizada pelo Agente durante a auditoria."""

    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    summary_result: str = ""
    candidates_found: int = 0
    best_similarity_pct: float = 0.0


class AgentFinalJudgment(BaseModel):
    """Schema de saída estruturada produzida pelo Agente Auditor após o ciclo de Tool-Calling."""

    status_final: VerdictStatus = Field(
        description="Status único conforme Matriz de Decisão: 'VÁLIDA', 'SUSPEITA (Revisar)' ou 'ALUCINADA'."
    )
    categoria_taxonomia: HallucinationCategory = Field(
        description="Classificação específica segundo a Taxonomia de Alucinações (Seção 2) e RN05."
    )
    diagnostico_explicativo: str = Field(
        description="Justificativa clara e detalhada em português explicando o veredito (RF05)."
    )
    acao_recomendada: str = Field(
        description="Ação recomendada ao usuário conforme a Matriz de Decisão (Seção 4)."
    )


class ReferenceAuditResult(BaseModel):
    """Resultado consolidado da auditoria de uma única referência bibliográfica."""

    indice: int
    referencia_extraida: ParsedReference
    status_final: VerdictStatus
    categoria_taxonomia: HallucinationCategory
    diagnostico_explicativo: str
    acao_recomendada: str
    melhor_correspondencia_oficial: Optional[OfficialWorkMetadata] = None
    metricas: ComparisonMetrics = Field(default_factory=ComparisonMetrics)
    rastro_tools: List[ToolCallTrace] = Field(default_factory=list)


class AuditReport(BaseModel):
    """Relatório completo da auditoria com resumo quantitativo (RF06)."""

    arquivo_origem: str
    formato_origem: str
    data_hora_iso: str
    secao_referencias_isolada_preview: str = Field(
        default="",
        description="Amostra do bloco de referências isolado demonstrando conformidade com RNF02.",
    )
    total_analisado: int = 0
    total_valido: int = 0
    total_suspeito: int = 0
    total_alucinado: int = 0
    resultados: List[ReferenceAuditResult] = Field(default_factory=list)

    def recompute_totals(self) -> None:
        """Recalcula os contadores do resumo quantitativo a partir da lista de resultados."""
        self.total_analisado = len(self.resultados)
        self.total_valido = sum(
            1 for r in self.resultados if r.status_final == VerdictStatus.VALIDA
        )
        self.total_suspeito = sum(
            1 for r in self.resultados if r.status_final == VerdictStatus.SUSPEITA
        )
        self.total_alucinado = sum(
            1 for r in self.resultados if r.status_final == VerdictStatus.ALUCINADA
        )
