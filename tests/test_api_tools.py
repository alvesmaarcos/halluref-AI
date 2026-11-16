"""Testes unitários para o ReferenceAuditToolkit e BibliographicAuditorAgent com mocks das APIs."""

from typing import List, Optional, Tuple

from aluc.agent.auditor_agent import BibliographicAuditorAgent
from aluc.config import AlucConfig
from aluc.schemas import (
    HallucinationCategory,
    OfficialWorkMetadata,
    ParsedReference,
    VerdictStatus,
)


class FakeCrossrefClient:
    def resolve_doi(
        self, raw_doi: str
    ) -> Tuple[str, Optional[OfficialWorkMetadata]]:
        if "10.1038/nature14539" in raw_doi:
            return (
                "RESOLVIDO",
                OfficialWorkMetadata(
                    fonte_api="Crossref",
                    titulo_oficial="Deep learning",
                    autores_oficiais=["Yann LeCun", "Yoshua Bengio", "Geoffrey Hinton"],
                    ano_oficial=2015,
                    veiculo_oficial="Nature",
                    doi_oficial="10.1038/nature14539",
                ),
            )
        return "INEXISTENTE_404", None

    def search_by_title(
        self, title: str, rows: int = 5
    ) -> List[OfficialWorkMetadata]:
        if "deep learning" in title.lower():
            return [
                OfficialWorkMetadata(
                    fonte_api="Crossref",
                    titulo_oficial="Deep learning",
                    autores_oficiais=["Yann LeCun", "Yoshua Bengio", "Geoffrey Hinton"],
                    ano_oficial=2015,
                    veiculo_oficial="Nature",
                    doi_oficial="10.1038/nature14539",
                )
            ]
        return []


class FakeOpenAlexClient:
    def resolve_doi(self, raw_doi: str) -> Optional[OfficialWorkMetadata]:
        return None

    def search_by_title(
        self, title: str, per_page: int = 5
    ) -> List[OfficialWorkMetadata]:
        if "attention is all you need" in title.lower():
            return [
                OfficialWorkMetadata(
                    fonte_api="OpenAlex",
                    titulo_oficial="Attention Is All You Need",
                    autores_oficiais=[
                        "Ashish Vaswani",
                        "Noam Shazeer",
                        "Niki Parmar",
                        "Jakob Uszkoreit",
                    ],
                    ano_oficial=2017,
                    veiculo_oficial="Advances in Neural Information Processing Systems",
                )
            ]
        return []


class FakeSemanticScholarClient:
    def search_by_title(
        self, title: str, limit: int = 5
    ) -> List[OfficialWorkMetadata]:
        return []


def test_auditor_agent_cascade_and_sample_fixture():
    """Valida a auditoria das 8 referências de `sample_references.bib` cobrindo todas as regras."""
    cfg = AlucConfig(gemini_api_key="")  # Executa com determinismo sobre os mocks
    agent = BibliographicAuditorAgent(
        config=cfg,
        crossref=FakeCrossrefClient(),  # type: ignore[arg-type]
        openalex=FakeOpenAlexClient(),  # type: ignore[arg-type]
        semantic_scholar=FakeSemanticScholarClient(),  # type: ignore[arg-type]
    )

    report = agent.audit_file("tests/fixtures/sample_references.bib")

    assert report.total_analisado == 8
    assert report.total_valido == 1
    assert report.total_suspeito == 3
    assert report.total_alucinado == 4

    by_idx = {r.indice: r for r in report.resultados}

    # [1] LeCun et al. (2015) -> VÁLIDA via resolve_doi_tool
    assert by_idx[1].status_final == VerdictStatus.VALIDA
    assert by_idx[1].categoria_taxonomia == HallucinationCategory.NONE
    assert by_idx[1].rastro_tools[0].tool_name == "resolve_doi_tool"

    # [2] Ghost Reference -> ALUCINADA (consultou Crossref -> OpenAlex -> Semantic Scholar)
    assert by_idx[2].status_final == VerdictStatus.ALUCINADA
    assert by_idx[2].categoria_taxonomia == HallucinationCategory.GHOST_REFERENCE
    assert [t.tool_name for t in by_idx[2].rastro_tools] == [
        "search_crossref_tool",
        "search_openalex_tool",
        "search_semantic_scholar_tool",
    ]

    # [3] Quimera (Attention Is All You Need encontrado no OpenAlex, mas autores falsos) -> ALUCINADA
    assert by_idx[3].status_final == VerdictStatus.ALUCINADA
    assert by_idx[3].categoria_taxonomia == HallucinationCategory.CHIMERA

    # [4] DOI Fake 404 + título fantasma -> ALUCINADA (DOI_FABRICATION)
    assert by_idx[4].status_final == VerdictStatus.ALUCINADA
    assert by_idx[4].categoria_taxonomia == HallucinationCategory.DOI_FABRICATION

    # [5] DOI Hijacked (DOI da Nature 14539 usado em título de algas marinhas) -> ALUCINADA
    assert by_idx[5].status_final == VerdictStatus.ALUCINADA
    assert by_idx[5].categoria_taxonomia == HallucinationCategory.DOI_HIJACKING

    # [6] Distorção de Ano (2022 vs 2015 = 7 anos > 2) -> SUSPEITA
    assert by_idx[6].status_final == VerdictStatus.SUSPEITA
    assert by_idx[6].categoria_taxonomia == HallucinationCategory.VENUE_OR_YEAR_DISTORTION

    # [7] Norma ABNT NBR 14724 -> SUSPEITA (RN05)
    assert by_idx[7].status_final == VerdictStatus.SUSPEITA
    assert (
        by_idx[7].categoria_taxonomia
        == HallucinationCategory.UNVERIFIABLE_GREY_LITERATURE
    )

    # [8] Portal UFC @misc -> SUSPEITA (RN05)
    assert by_idx[8].status_final == VerdictStatus.SUSPEITA
    assert (
        by_idx[8].categoria_taxonomia
        == HallucinationCategory.UNVERIFIABLE_GREY_LITERATURE
    )


def test_auditor_agent_gemini_interactions_tool_calling_loop():
    """Simula o ciclo completo de Function Calling da Interactions API (google-genai) no Agente Auditor."""

    class DummyStep:
        def __init__(self, step_type: str, **kwargs):
            self.type = step_type
            for k, v in kwargs.items():
                setattr(self, k, v)

    class DummyInteraction:
        def __init__(self, interaction_id: str, steps: list, output_text: str = ""):
            self.id = interaction_id
            self.steps = steps
            self.output_text = output_text

    class DummyInteractionsResource:
        def __init__(self):
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            turn = len(self.calls)
            if turn == 1:
                # Turno 1: Modelo solicita chamada da tool `resolve_doi_tool`
                return DummyInteraction(
                    interaction_id="inter_turn_1",
                    steps=[
                        DummyStep(
                            "function_call",
                            id="call_doi_1",
                            name="resolve_doi_tool",
                            arguments={"doi": "10.1038/nature14539"},
                        )
                    ],
                )
            # Turno 2: Modelo recebe function_result e retorna o veredito estruturado
            assert kwargs.get("previous_interaction_id") == "inter_turn_1"
            fn_results = kwargs.get("input")
            assert isinstance(fn_results, list)
            assert fn_results[0]["type"] == "function_result"
            assert fn_results[0]["call_id"] == "call_doi_1"
            return DummyInteraction(
                interaction_id="inter_turn_2",
                steps=[],
                output_text=(
                    '{"status_final": "VÁLIDA", '
                    '"categoria_taxonomia": "Nenhuma (Referência Íntegra)", '
                    '"diagnostico_explicativo": "DOI 10.1038/nature14539 validado no Crossref com 100% de similaridade.", '
                    '"acao_recomendada": "Nenhuma ação necessária. Referência íntegra."}'
                ),
            )

    cfg = AlucConfig(gemini_api_key="")
    agent = BibliographicAuditorAgent(
        config=cfg,
        crossref=FakeCrossrefClient(),  # type: ignore[arg-type]
        openalex=FakeOpenAlexClient(),  # type: ignore[arg-type]
        semantic_scholar=FakeSemanticScholarClient(),  # type: ignore[arg-type]
    )

    dummy_resource = DummyInteractionsResource()

    class DummyGenAIClient:
        interactions = dummy_resource

    agent.genai_client = DummyGenAIClient()  # type: ignore[assignment]

    ref = ParsedReference(
        texto_original="LeCun, Bengio, Hinton (2015) Deep learning",
        titulo="Deep learning",
        autores=["LeCun, Yann", "Bengio, Yoshua", "Hinton, Geoffrey"],
        ano=2015,
        doi="10.1038/nature14539",
    )
    res = agent.audit_single_reference(1, ref)

    assert len(dummy_resource.calls) == 2
    assert res.status_final == VerdictStatus.VALIDA
    assert "100% de similaridade" in res.diagnostico_explicativo
    assert len(res.rastro_tools) == 1
    assert res.rastro_tools[0].tool_name == "resolve_doi_tool"

