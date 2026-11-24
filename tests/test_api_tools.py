"""Testes unitários para o ReferenceAuditToolkit e BibliographicAuditorAgent com mocks das APIs."""

from io import BytesIO
import json
import time
from types import SimpleNamespace
from typing import List, Optional, Tuple

import httpx
from fpdf import FPDF
from pypdf import PdfReader

from aluc.agent.auditor_agent import BibliographicAuditorAgent
from aluc.clients.http_client import PoliteHttpClient
from aluc.config import AlucConfig
from aluc.exporters import (
    export_report_to_json,
    export_report_to_markdown,
    export_report_to_pdf,
)
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


class FakeGemini:
    def __init__(self, respond):
        self.interactions = self
        self.respond = respond
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        answer = self.respond(kwargs, len(self.calls))
        return SimpleNamespace(output_text=json.dumps(answer))


def _agent():
    return BibliographicAuditorAgent(
        config=AlucConfig(),
        crossref=FakeCrossrefClient(),
        openalex=FakeOpenAlexClient(),
        semantic_scholar=FakeSemanticScholarClient(),
    )


def _make_pdf(path, text):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(0, 8, text)
    pdf.output(path)


def test_clear_bibtex_does_not_call_gemini(tmp_path):
    agent = _agent()
    gemini = FakeGemini(lambda *_: {})
    agent.genai_client = agent.parser.client = gemini
    bib = tmp_path / "clear.bib"
    bib.write_text(
        "@article{clear, title={Deep learning}, year={2015}, "
        "author={Yann LeCun and Yoshua Bengio and Geoffrey Hinton}, "
        "doi={10.1038/nature14539}}",
        encoding="utf-8",
    )

    report = agent.audit_file(bib)

    assert not gemini.calls
    assert report.total_valido == 1


def test_pdf_budget_batch_and_verified_correction(tmp_path):
    agent = _agent()
    path = tmp_path / "article.pdf"
    _make_pdf(path, "Confidential manuscript body.\n\nReferences\nBibliography with unusual formatting")
    events = []
    references = [
        ParsedReference(
            texto_original="Cited work",
            titulo="Deep learning" if index in (2, 3) else "Unknown work",
            autores=["Yann LeCun", "Yoshua Bengio", "Geoffrey Hinton"],
            ano=2015,
            doi="10.5555/fake" if index == 2 else None,
        ).model_dump()
        for index in range(1, 14)
    ]

    def respond(kwargs, attempt):
        assert "Confidential manuscript body" not in kwargs["input"]
        if attempt == 1:
            assert "estruturar a bibliografia" in events[-1]
            assert "Bibliography with unusual formatting" in kwargs["input"]
            return {"referencias": references}
        batch = json.loads(kwargs["input"])
        assert len(batch) == 10
        assert batch[0]["indice"] == 2
        assert 3 not in {item["indice"] for item in batch}
        if attempt == 2:
            assert "planejar buscas" in events[-1]
            return {"buscas": [
                {"indice": 2, "provedor": "Crossref", "consulta": "Deep learning"},
                {"indice": 1, "provedor": "Crossref", "consulta": "Deep learning"},
                {"indice": 99, "provedor": "Crossref", "consulta": "Deep learning"},
                {"indice": 2, "provedor": "Crossref", "consulta": "LeCun Deep learning"},
                {"indice": 2, "provedor": "Crossref", "consulta": "Excess search"},
                {"indice": 2, "provedor": "Unlisted", "consulta": "Deep learning"},
            ]}
        assert "avaliar os registros" in events[-1]
        assert len(batch[0]["candidatos"]) == 1
        return {"escolhas": [
            {"indice": 2, "candidato": 99},
            {"indice": 99, "candidato": 1},
            {"indice": 2, "candidato": 1},
            {"indice": 1, "candidato": 1},
        ]}

    gemini = FakeGemini(respond)
    agent.genai_client = agent.parser.client = gemini
    report = agent.audit_file(path, lambda _, __, message: events.append(message))

    assert len(gemini.calls) == 3
    assert report.chamadas_gemini_extracao == 1
    assert report.chamadas_gemini_investigacao == 2
    assert report.total_analisado == 13
    assert report.resultados[0].correcao_verificada is None
    corrected = report.resultados[1]
    assert corrected.categoria_taxonomia == HallucinationCategory.DOI_FABRICATION
    assert corrected.referencia_extraida.doi == "10.5555/fake"
    assert corrected.correcao_verificada.registro.doi_oficial == "10.1038/nature14539"
    assert "@misc{aluc2" in corrected.correcao_verificada.bibtex
    assert sum(trace.tool_name == "busca_adicional" for trace in corrected.rastro_tools) == 2
    assert report.resultados[-1].estado_investigacao == "Revisão manual"
    assert "Correção verificada" in export_report_to_markdown(report)
    assert json.loads(export_report_to_json(report))["chamadas_gemini_investigacao"] == 2
    pdf = PdfReader(BytesIO(export_report_to_pdf(report)))
    pdf_text = "\n".join(page.extract_text() for page in pdf.pages)
    assert "Correção verificada" in pdf_text
    assert "aluc2" in pdf_text


def test_pdf_without_bibliography_never_calls_gemini(tmp_path):
    path = tmp_path / "manuscript.pdf"
    _make_pdf(path, "Introduction\nReferences to confidential material appear in the appendix.\nPrivate conclusion.")
    agent = _agent()
    gemini = FakeGemini(lambda *_: {})
    agent.genai_client = agent.parser.client = gemini

    report = agent.audit_file(path)

    assert not gemini.calls
    assert not report.resultados
    assert not report.secao_referencias_isolada_preview
    assert ".bib" in report.avisos[0]


def test_invalid_planning_response_stops_before_second_call():
    agent = _agent()
    gemini = FakeGemini(lambda *_: {"buscas": "invalid"})
    agent.genai_client = gemini

    report = agent.audit_file("tests/fixtures/sample_references.bib")

    assert report.chamadas_gemini_investigacao == len(gemini.calls) == 1
    assert report.resultados[1].estado_investigacao == "Revisão manual"


def test_lookup_failures_keep_reference_in_review_and_report_progress():
    events = []
    requests = []

    def respond(request):
        host = request.url.host
        assert f"Aguardando resposta de {host}" in events[-1]
        requests.append(host)
        time.sleep(0.01)
        return httpx.Response(429 if host == "api.crossref.org" else 200, json={})

    cfg = AlucConfig(
        crossref_min_interval_sec=0,
        openalex_min_interval_sec=0,
        semantic_scholar_min_interval_sec=0,
    )
    http = PoliteHttpClient(cfg)
    http.close()
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        http._client = client
        agent = BibliographicAuditorAgent(cfg, http_client=http)
        result = agent.audit_single_reference(
            1,
            ParsedReference(texto_original="Not found", titulo="Not found", autores=["Jane Doe"]),
            events.append,
        )

    assert set(requests) == {"api.crossref.org", "api.openalex.org", "api.semanticscholar.org"}
    assert result.status_final == VerdictStatus.SUSPEITA
    assert result.categoria_taxonomia == HallucinationCategory.CONSULTA_INCONCLUSIVA
    assert result.falhas_consulta == ["api.crossref.org"]


def test_hijacked_doi_correction_preserves_original_verdict(tmp_path):
    path = tmp_path / "hijacked.bib"
    path.write_text(
        "@article{entry,title={Deep learning},"
        "author={Yann LeCun and Yoshua Bengio and Geoffrey Hinton},"
        "year={2015},doi={10.5555/swapped}}",
        encoding="utf-8",
    )

    class WrongDoiCrossref(FakeCrossrefClient):
        def resolve_doi(self, raw_doi):
            return "RESOLVIDO", OfficialWorkMetadata(
                fonte_api="Crossref",
                titulo_oficial="Marine algae in the Amazon",
                doi_oficial=raw_doi,
            )

    agent = _agent()
    agent.crossref = WrongDoiCrossref()
    agent.genai_client = FakeGemini(
        lambda _, attempt: {"buscas": [
            {"indice": 1, "provedor": "Crossref", "consulta": "Deep learning"}
        ]} if attempt == 1 else {"escolhas": [{"indice": 1, "candidato": 1}]}
    )

    report = agent.audit_file(path)

    result = report.resultados[0]
    assert result.status_final == VerdictStatus.ALUCINADA
    assert result.categoria_taxonomia == HallucinationCategory.DOI_HIJACKING
    assert result.melhor_correspondencia_oficial.doi_oficial == "10.5555/swapped"
    assert result.correcao_verificada.registro.doi_oficial == "10.1038/nature14539"
    assert all(
        not call["automatic_continuation"] and not call["store"]
        for call in agent.genai_client.calls
    )


def test_doi_case_and_pdf_transcription_are_handled_separately():
    canonical_doi = "10.1109/isec64801.2025.11147384"
    title = "Prompt Engineering: A Comparative Study of Prompting Techniques in AI Language Models"
    work = OfficialWorkMetadata(
        fonte_api="Crossref",
        titulo_oficial=title,
        autores_oficiais=["Jothan Almeida"],
        ano_oficial=2025,
        doi_oficial=canonical_doi,
    )

    class Crossref:
        def resolve_doi(self, doi):
            assert doi == doi.lower()
            return ("RESOLVIDO", work) if doi == canonical_doi else ("INEXISTENTE_404", None)

        def search_by_title(self, title, **kwargs):
            return [work]

    agent = _agent()
    agent.crossref = Crossref()
    for doi, from_pdf, expected in [
        ("10.1109/ISEC64801.2025.11147384", False, VerdictStatus.VALIDA),
        ("10.1109/1SEC64801.2025.11147384", True, VerdictStatus.VALIDA),
        ("10.1109/1SEC64801.2025.11147384", False, VerdictStatus.SUSPEITA),
        ("10.1109/2SEC64801.2025.11147384", True, VerdictStatus.SUSPEITA),
    ]:
        ref = ParsedReference(
            texto_original=title, titulo=title, autores=["Jothan Almeida"], ano=2025, doi=doi
        )
        result = agent.audit_single_reference(1, ref, from_pdf=from_pdf)

        assert result.status_final == expected
        assert result.referencia_extraida.doi == doi
        if from_pdf and expected == VerdictStatus.VALIDA:
            assert canonical_doi in result.diagnostico_explicativo
            assert "caractere visualmente semelhante" in result.diagnostico_explicativo
