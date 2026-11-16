"""Testes unitários para as Regras de Negócio RN01 a RN05 e Matriz de Decisão (Seções 3 e 4)."""

from aluc.rules.metrics import (
    calculate_title_similarity,
    classify_title_similarity,
    compute_comparison_metrics,
    evaluate_author_intersection,
    evaluate_decision_matrix,
    evaluate_scope_exception_rn05,
    evaluate_year_tolerance,
    extract_surname,
    normalize_text,
)
from aluc.schemas import (
    HallucinationCategory,
    OfficialWorkMetadata,
    ParsedReference,
    ReferenceType,
    VerdictStatus,
)


def test_normalize_text_and_title_similarity_rn02():
    """Verifica normalização (acentos, caixa, pontuação) e faixas de similaridade da RN02."""
    t1 = "Atenção e Memória: Uma Revisão Sistemática!"
    t2 = "atencao e memoria uma revisao sistematica"
    assert normalize_text(t1) == t2

    sim_exact = calculate_title_similarity(t1, t2)
    assert sim_exact == 100.0
    assert classify_title_similarity(sim_exact) == "FORTE"

    # Título truncado sem subtítulo (entre 60% e 84%)
    full_title = "Deep Residual Learning for Image Recognition in Autonomous Vehicles"
    truncated_title = "Deep Residual Learning for Image Recognition"
    sim_partial = calculate_title_similarity(truncated_title, full_title)
    assert 60.0 <= sim_partial < 85.0
    assert classify_title_similarity(sim_partial) == "PARCIAL"

    # Título sem relação (< 60%)
    unrelated = "Marine Biology and Coral Reef Calcification Rates"
    sim_low = calculate_title_similarity(truncated_title, unrelated)
    assert sim_low < 60.0
    assert classify_title_similarity(sim_low) == "BAIXA"


def test_extract_surname_and_author_intersection_rn03():
    """Verifica extração de sobrenomes e critérios de interseção de autoria (RN03)."""
    assert extract_surname("Vaswani, Ashish") == "vaswani"
    assert extract_surname("Ashish Vaswani") == "vaswani"
    assert extract_surname("João da Silva Filho") == "silva"
    assert extract_surname("Silva Neto, Antônio") == "silva"

    official = ["Ashish Vaswani", "Noam Shazeer", "Niki Parmar", "Jakob Uszkoreit"]

    # 1. Correspondência ALTA (1º autor coincide + >= 50% dos demais)
    cited_high = ["Vaswani, A.", "Shazeer, N.", "Parmar, N."]
    res_high = evaluate_author_intersection(cited_high, official)
    assert res_high["correspondencia_autoria"] == "ALTA"
    assert res_high["primeiro_autor_coincide"] is True

    # 2. Correspondência ALTA com 'et al.'
    cited_et_al = ["Vaswani, Ashish", "et al."]
    res_et_al = evaluate_author_intersection(cited_et_al, official)
    assert res_et_al["correspondencia_autoria"] == "ALTA"

    # 3. Correspondência PARCIAL (1º autor diverge, mas há coautor verdadeiro)
    cited_partial = ["Shazeer, Noam", "Vaswani, Ashish"]
    res_partial = evaluate_author_intersection(cited_partial, official)
    assert res_partial["correspondencia_autoria"] == "PARCIAL"
    assert res_partial["primeiro_autor_coincide"] is False

    # 4. Sem Interseção (0% - Quimera / Atribuição Falsa)
    cited_chimera = ["Pereira, Carlos", "Oliveira, Mariana"]
    res_chimera = evaluate_author_intersection(cited_chimera, official)
    assert res_chimera["correspondencia_autoria"] == "SEM_INTERSECAO"


def test_year_tolerance_rn04():
    """Verifica tolerância temporal de até 2 anos (RN04)."""
    diff_ok, is_ok = evaluate_year_tolerance(2019, 2017)
    assert diff_ok == 2
    assert is_ok is True

    diff_bad, is_bad = evaluate_year_tolerance(2023, 2017)
    assert diff_bad == 6
    assert is_bad is False


def test_scope_exceptions_rn05():
    """Verifica detecção de Normas Técnicas, Legislação e Páginas Web (RN05)."""
    norm_ref = ParsedReference(
        texto_original="ABNT NBR 14724:2011",
        titulo="ABNT NBR 14724: Informação e documentação",
        autores=["ABNT"],
        ano=2011,
        tipo_inferido=ReferenceType.STANDARD,
    )
    is_exc, reason = evaluate_scope_exception_rn05(norm_ref)
    assert is_exc is True
    assert "RN05" in (reason or "")

    web_ref = ParsedReference(
        texto_original="@misc{site, url={https://ufc.br}}",
        titulo="Portal da UFC",
        url="https://ufc.br",
        tipo_inferido=ReferenceType.WEBPAGE,
    )
    is_exc_web, _ = evaluate_scope_exception_rn05(web_ref)
    assert is_exc_web is True


def test_decision_matrix_all_scenarios():
    """Testa todos os cenários da Matriz de Decisão (Seção 4 do DRS)."""
    official_dl = OfficialWorkMetadata(
        fonte_api="Crossref",
        titulo_oficial="Deep learning",
        autores_oficiais=["Yann LeCun", "Yoshua Bengio", "Geoffrey Hinton"],
        ano_oficial=2015,
        veiculo_oficial="Nature",
        doi_oficial="10.1038/nature14539",
    )

    # Cenário 1: VÁLIDA
    ref_valid = ParsedReference(
        texto_original="LeCun, Bengio, Hinton (2015) Deep learning",
        titulo="Deep learning",
        autores=["LeCun, Yann", "Bengio, Yoshua", "Hinton, Geoffrey"],
        ano=2015,
        doi="10.1038/nature14539",
    )
    m_valid = compute_comparison_metrics(ref_valid, official_dl, "RESOLVIDO")
    status, cat, _ = evaluate_decision_matrix(m_valid)
    assert status == VerdictStatus.VALIDA
    assert cat == HallucinationCategory.NONE

    # Cenário 2: ALUCINADA - DOI Cruzado (Hijacked - RN01 Critério 2)
    ref_hijack = ParsedReference(
        texto_original="Ribeiro (2021) Marine Algae Polymers. doi:10.1038/nature14539",
        titulo="Synthesizing Novel Biodegradable Polymers from Marine Algae",
        autores=["Ribeiro, Gustavo"],
        ano=2021,
        doi="10.1038/nature14539",
    )
    m_hijack = compute_comparison_metrics(ref_hijack, official_dl, "RESOLVIDO")
    status, cat, _ = evaluate_decision_matrix(m_hijack)
    assert status == VerdictStatus.ALUCINADA
    assert cat == HallucinationCategory.DOI_HIJACKING

    # Cenário 3: ALUCINADA - Quimera (Título >= 85%, mas 0% de interseção nos autores - RN03)
    ref_chimera = ParsedReference(
        texto_original="Silva, Santos (2015) Deep learning. Nature.",
        titulo="Deep learning",
        autores=["Silva, Roberto", "Santos, Fernanda"],
        ano=2015,
    )
    m_chimera = compute_comparison_metrics(ref_chimera, official_dl, "NAO_INFORMADO")
    status, cat, _ = evaluate_decision_matrix(m_chimera)
    assert status == VerdictStatus.ALUCINADA
    assert cat == HallucinationCategory.CHIMERA

    # Cenário 4: ALUCINADA - Invenção Total (Ghost Reference - RN02 < 60%)
    ref_ghost = ParsedReference(
        texto_original="Almeida (2024) Quantum Sub-Symbolic Hyper-Networks",
        titulo="Quantum Sub-Symbolic Hyper-Networks in Zero Gravity",
        autores=["Almeida, Lucas"],
        ano=2024,
    )
    m_ghost = compute_comparison_metrics(ref_ghost, None, "NAO_INFORMADO")
    status, cat, _ = evaluate_decision_matrix(m_ghost)
    assert status == VerdictStatus.ALUCINADA
    assert cat == HallucinationCategory.GHOST_REFERENCE

    # Cenário 5: SUSPEITA - Distorção Temporal (> 2 anos - RN04)
    ref_year = ParsedReference(
        texto_original="LeCun, Bengio, Hinton (2022) Deep learning",
        titulo="Deep learning",
        autores=["LeCun, Yann", "Bengio, Yoshua", "Hinton, Geoffrey"],
        ano=2022,
    )
    m_year = compute_comparison_metrics(ref_year, official_dl, "NAO_INFORMADO")
    status, cat, _ = evaluate_decision_matrix(m_year)
    assert status == VerdictStatus.SUSPEITA
    assert cat == HallucinationCategory.VENUE_OR_YEAR_DISTORTION

    # Cenário 6: SUSPEITA - Exceção RN05 (Norma técnica ausente nas APIs)
    ref_rn05 = ParsedReference(
        texto_original="ABNT NBR 14724:2011",
        titulo="ABNT NBR 14724: Informação e documentação",
        autores=["ABNT"],
        ano=2011,
        tipo_inferido=ReferenceType.STANDARD,
    )
    m_rn05 = compute_comparison_metrics(ref_rn05, None, "NAO_INFORMADO")
    status, cat, _ = evaluate_decision_matrix(m_rn05)
    assert status == VerdictStatus.SUSPEITA
    assert cat == HallucinationCategory.UNVERIFIABLE_GREY_LITERATURE
