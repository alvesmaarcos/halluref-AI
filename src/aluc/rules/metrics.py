"""Implementação das Regras de Negócio RN01 a RN05 e Matriz de Decisão (Seções 3 e 4 do DRS)."""

from __future__ import annotations

import re
import unicodedata
from typing import List, Optional, Tuple
from rapidfuzz import fuzz

from aluc.schemas import (
    ComparisonMetrics,
    HallucinationCategory,
    OfficialWorkMetadata,
    ParsedReference,
    ReferenceType,
    VerdictStatus,
)

# Sufixos familiares que não são o sobrenome principal quando isolados no fim do nome
SUFFIX_TOKENS = {"jr", "junior", "filho", "neto", "sobrinho", "ii", "iii", "iv", "sr"}
ET_AL_TOKENS = {"et al", "et al.", "others"}


def normalize_text(text: str) -> str:
    """Normaliza uma string conforme RN02:
    - remoção de acentos (decomposição NFKD)
    - conversão para minúsculas
    - remoção de pontuação/símbolos
    - colapso de espaços múltiplos
    """
    if not text:
        return ""
    # Decompõe caracteres acentuados e remove marcas diacríticas
    nfkd = unicodedata.normalize("NFKD", text)
    without_accents = "".join(ch for ch in nfkd if not unicodedata.combining(ch))
    lowered = without_accents.lower()
    # Substitui qualquer caractere não alfanumérico por espaço
    alnum_only = re.sub(r"[^a-z0-9\s]", " ", lowered)
    return re.sub(r"\s+", " ", alnum_only).strip()


def calculate_title_similarity(cited_title: str, official_title: str) -> float:
    """Calcula a similaridade textual (0.0 a 100.0) entre dois títulos após normalização (RN01, RN02).

    Utiliza o máximo entre `fuzz.ratio` (ordem exata) e `fuzz.token_sort_ratio` (tolerante a
    inversões pontuais de termos), mantendo penalidade justa quando há truncamento ou palavras diferentes.
    """
    norm_cited = normalize_text(cited_title)
    norm_official = normalize_text(official_title)

    if not norm_cited or not norm_official:
        return 0.0

    score_ratio = fuzz.ratio(norm_cited, norm_official)
    score_token_sort = fuzz.token_sort_ratio(norm_cited, norm_official)
    return round(float(max(score_ratio, score_token_sort)), 2)


def classify_title_similarity(similarity_pct: float) -> str:
    """Classifica o percentual de similaridade nos limiares da RN02:
    - >= 85%: 'FORTE' (Título confirmado)
    - 60% a 84.99%: 'PARCIAL' (Título divergente ou truncado)
    - < 60%: 'BAIXA' (Título não encontrado / incompatível)
    """
    if similarity_pct >= 85.0:
        return "FORTE"
    if similarity_pct >= 60.0:
        return "PARCIAL"
    return "BAIXA"


def extract_surname(author_name: str) -> str:
    """Extrai o sobrenome principal normalizado de um autor.

    Suporta formatos:
    - 'Sobrenome, Nome Inicial.' -> 'sobrenome'
    - 'Nome Inicial. Sobrenome' -> 'sobrenome'
    - Trata sufixos como 'Jr.', 'Filho', 'Neto' (ex: 'Silva Filho, João' ou 'João Silva Filho').
    """
    if not author_name:
        return ""

    cleaned = author_name.strip()
    if normalize_text(cleaned) in ET_AL_TOKENS:
        return ""

    # Caso 'Sobrenome, Nome'
    if "," in cleaned:
        surname_part = cleaned.split(",", 1)[0].strip()
        tokens = normalize_text(surname_part).split()
        if not tokens:
            return ""
        if len(tokens) > 1 and tokens[-1] in SUFFIX_TOKENS:
            return tokens[-2]
        return tokens[-1]

    # Caso 'Nome Do Meio Sobrenome'
    tokens = normalize_text(cleaned).split()
    if not tokens:
        return ""
    if len(tokens) > 1 and tokens[-1] in SUFFIX_TOKENS:
        return tokens[-2]
    return tokens[-1]


def extract_surnames_list(authors: List[str]) -> Tuple[List[str], bool]:
    """Retorna a lista de sobrenomes extraídos e uma flag indicando se havia 'et al.'."""
    surnames: List[str] = []
    has_et_al = False

    for raw in authors:
        norm_raw = normalize_text(raw)
        if not norm_raw:
            continue
        if "et al" in norm_raw or norm_raw == "others":
            has_et_al = True
            # Se o texto tiver "Vaswani et al.", ainda extrai "vaswani" antes do et al
            cleaned_before = re.sub(r"\bet\s+al\b.*", "", norm_raw).strip()
            if cleaned_before:
                s = extract_surname(cleaned_before)
                if s and s not in {"et", "al"}:
                    surnames.append(s)
            continue

        s = extract_surname(raw)
        if s:
            surnames.append(s)

    return surnames, has_et_al


def _surnames_match(s1: str, s2: str) -> bool:
    """Verifica se dois sobrenomes normalizados coincidem (exato ou distância de 1 caractere em nomes longos)."""
    if not s1 or not s2:
        return False
    if s1 == s2:
        return True
    if len(s1) >= 6 and len(s2) >= 6 and fuzz.ratio(s1, s2) >= 88.0:
        return True
    return False


def evaluate_author_intersection(
    cited_authors: List[str], official_authors: List[str]
) -> dict:
    """Avalia a interseção de autoria conforme RN03 (Anti-Quimera).

    Critérios RN03:
    - Correspondência Total/Alta ('ALTA'): O sobrenome do primeiro autor coincide E
      pelo menos 50% dos demais sobrenomes coincidem.
    - Correspondência Parcial ('PARCIAL'): Pelo menos um sobrenome coincide, mas o primeiro
      autor diverge ou há omissão/divergência de coautores (sem uso de et al.).
    - Sem Interseção ('SEM_INTERSECAO' / 0%): Nenhum sobrenome citado coincide com os autores
      reais do artigo encontrado -> Alucinação por Quimera / Atribuição Falsa.
    """
    cited_surnames, has_et_al = extract_surnames_list(cited_authors)
    official_surnames, _ = extract_surnames_list(official_authors)

    if not cited_surnames or not official_surnames:
        return {
            "correspondencia_autoria": "NAO_AVALIADO",
            "primeiro_autor_coincide": False,
            "intersecao_demais_autores_pct": 0.0,
            "sobrenomes_citados": cited_surnames,
            "sobrenomes_oficiais": official_surnames,
            "sobrenomes_em_comum": [],
        }

    # Verifica interseção global
    matched_cited: List[str] = []
    for cs in cited_surnames:
        if any(_surnames_match(cs, os_name) for os_name in official_surnames):
            matched_cited.append(cs)

    if not matched_cited:
        return {
            "correspondencia_autoria": "SEM_INTERSECAO",
            "primeiro_autor_coincide": False,
            "intersecao_demais_autores_pct": 0.0,
            "sobrenomes_citados": cited_surnames,
            "sobrenomes_oficiais": official_surnames,
            "sobrenomes_em_comum": [],
        }

    first_author_match = _surnames_match(cited_surnames[0], official_surnames[0])

    remaining_cited = cited_surnames[1:]
    remaining_official = official_surnames[1:]

    if not remaining_cited:
        # Apenas 1 autor citado no documento
        if len(official_surnames) == 1 or has_et_al:
            others_overlap_pct = 100.0
        else:
            # Omitiu coautores sem usar 'et al.' -> RN03 classifica como Correspondência Parcial
            others_overlap_pct = 0.0
    else:
        matched_remaining = sum(
            1
            for cs in remaining_cited
            if any(_surnames_match(cs, os_name) for os_name in official_surnames)
        )
        # Calcula proporção sobre os demais autores citados (e verifica se omitiu quase todos sem et al.)
        denominator = len(remaining_cited)
        if not has_et_al and len(remaining_official) > len(remaining_cited) * 2:
            denominator = len(remaining_official)
        others_overlap_pct = round((matched_remaining / max(1, denominator)) * 100.0, 2)

    if first_author_match and others_overlap_pct >= 50.0:
        tier = "ALTA"
    else:
        tier = "PARCIAL"

    return {
        "correspondencia_autoria": tier,
        "primeiro_autor_coincide": first_author_match,
        "intersecao_demais_autores_pct": others_overlap_pct,
        "sobrenomes_citados": cited_surnames,
        "sobrenomes_oficiais": official_surnames,
        "sobrenomes_em_comum": matched_cited,
    }


def evaluate_year_tolerance(
    cited_year: Optional[int], official_year: Optional[int]
) -> Tuple[Optional[int], Optional[bool]]:
    """Avalia a tolerância temporal de publicação conforme RN04.

    Retorna (diferenca_absoluta_anos, ano_aceitavel).
    - Diferença <= 2 anos: Aceitável (True)
    - Diferença > 2 anos: Suspeita (False)
    """
    if cited_year is None or official_year is None:
        return None, None
    diff = abs(int(cited_year) - int(official_year))
    return diff, (diff <= 2)


def evaluate_scope_exception_rn05(ref: ParsedReference) -> Tuple[bool, Optional[str]]:
    """Verifica se a referência se enquadra nas Exceções de Escopo da RN05:
    Normas técnicas (ISO, ABNT, NBR, IEEE), legislação, páginas web (@misc / URLs),
    relatórios técnicos, monografias/teses locais ou livros sem DOI.
    """
    combined = f"{ref.titulo} {ref.veiculo or ''} {ref.texto_original}".upper()

    # 1. Normas técnicas (ABNT, NBR, ISO, IEEE Std, RFC, W3C)
    if ref.tipo_inferido == ReferenceType.STANDARD or any(
        kw in combined
        for kw in [
            "ABNT",
            "NBR ",
            "ISO ",
            "ISO/",
            "IEC ",
            "IEEE STD",
            "NORMA TÉCNICA",
            "ASSOCIAÇÃO BRASILEIRA DE NORMAS TÉCNICAS",
        ]
    ):
        return True, "Norma técnica (ISO/ABNT/NBR/IEEE) — RN05"

    # 2. Legislação / Documentos governamentais
    if ref.tipo_inferido == ReferenceType.LEGISLATION or any(
        kw in combined
        for kw in [
            "LEI Nº",
            "LEI N.",
            "DECRETO Nº",
            "PORTARIA Nº",
            "RESOLUÇÃO Nº",
            "DIÁRIO OFICIAL",
            "CONSTITUIÇÃO FEDERAL",
        ]
    ):
        return True, "Legislação ou documento normativo oficial — RN05"

    # 3. Páginas web / @misc com URL e sem DOI de periódico
    if ref.tipo_inferido == ReferenceType.WEBPAGE or (
        not ref.doi
        and (
            "@MISC" in combined
            or "@ONLINE" in combined
            or "DISPONÍVEL EM:" in combined
            or "AVAILABLE AT:" in combined
            or "ACESSO EM:" in combined
            or "ACCESSED:" in combined
            or (ref.url and not ref.veiculo)
        )
    ):
        return True, "Página web / recurso online (@misc / URL) — RN05"

    # 4. Monografias, dissertações, teses ou relatórios técnicos locais sem DOI
    if not ref.doi and (
        ref.tipo_inferido in {ReferenceType.THESIS, ReferenceType.TECHREPORT}
        or any(
            kw in combined
            for kw in [
                "TRABALHO DE CONCLUSÃO DE CURSO",
                "MONOGRAFIA",
                "DISSERTAÇÃO (MESTRADO)",
                "TESE (DOUTORADO)",
                "RELATÓRIO TÉCNICO",
                "TECHNICAL REPORT",
            ]
        )
    ):
        return True, "Monografia, tese ou relatório técnico local — RN05"

    # 5. Livros sem DOI
    if not ref.doi and (
        ref.tipo_inferido == ReferenceType.BOOK
        or any(kw in combined for kw in ["@BOOK{", "EDITORA ", "ISBN "])
    ):
        return True, "Livro ou capítulo sem indexação DOI — RN05"

    return False, None


def compute_comparison_metrics(
    ref: ParsedReference,
    official: Optional[OfficialWorkMetadata],
    doi_resolution_status: str = "NAO_INFORMADO",
) -> ComparisonMetrics:
    """Consolida todas as métricas das regras RN01 a RN05 entre a referência citada e um candidato oficial."""
    is_rn05, reason_rn05 = evaluate_scope_exception_rn05(ref)

    if official is None:
        return ComparisonMetrics(
            doi_informado=ref.doi,
            doi_resolvido=False,
            doi_status=doi_resolution_status,
            similaridade_titulo_pct=0.0,
            faixa_similaridade_titulo="NAO_ENCONTRADO",
            correspondencia_autoria="SEM_INTERSECAO",
            primeiro_autor_coincide=False,
            intersecao_demais_autores_pct=0.0,
            sobrenomes_citados=extract_surnames_list(ref.autores)[0],
            sobrenomes_oficiais=[],
            sobrenomes_em_comum=[],
            diferenca_ano=None,
            ano_aceitavel=None,
            excecao_escopo_rn05=is_rn05,
            motivo_rn05=reason_rn05,
        )

    sim_pct = calculate_title_similarity(ref.titulo, official.titulo_oficial)
    sim_tier = classify_title_similarity(sim_pct)
    author_eval = evaluate_author_intersection(ref.autores, official.autores_oficiais)
    year_diff, year_ok = evaluate_year_tolerance(ref.ano, official.ano_oficial)

    # Atualiza status do DOI se foi resolvido
    doi_status = doi_resolution_status
    if ref.doi and doi_status == "RESOLVIDO":
        if sim_pct < 60.0:
            doi_status = "CRUZADO_HIJACKED"
        else:
            doi_status = "VALIDO_CORRESPONDENTE"

    return ComparisonMetrics(
        doi_informado=ref.doi,
        doi_resolvido=(doi_status in {"VALIDO_CORRESPONDENTE", "CRUZADO_HIJACKED"}),
        doi_status=doi_status,
        similaridade_titulo_pct=sim_pct,
        faixa_similaridade_titulo=sim_tier,
        correspondencia_autoria=author_eval["correspondencia_autoria"],
        primeiro_autor_coincide=author_eval["primeiro_autor_coincide"],
        intersecao_demais_autores_pct=author_eval["intersecao_demais_autores_pct"],
        sobrenomes_citados=author_eval["sobrenomes_citados"],
        sobrenomes_oficiais=author_eval["sobrenomes_oficiais"],
        sobrenomes_em_comum=author_eval["sobrenomes_em_comum"],
        diferenca_ano=year_diff,
        ano_aceitavel=year_ok,
        excecao_escopo_rn05=is_rn05,
        motivo_rn05=reason_rn05,
    )


def evaluate_decision_matrix(
    metrics: ComparisonMetrics,
) -> Tuple[VerdictStatus, HallucinationCategory, str]:
    """Aplica a Matriz de Decisão (Seção 4 do DRS) sobre as métricas consolidadas.

    Retorna (status_final, categoria_taxonomia, acao_recomendada).
    """
    # 1. RN01 Critério 2: DOI Cruzado (Hijacked) -> ALUCINADA
    if metrics.doi_status == "CRUZADO_HIJACKED":
        return (
            VerdictStatus.ALUCINADA,
            HallucinationCategory.DOI_HIJACKING,
            "Remover a referência do artigo ou substituir por uma fonte real verificada.",
        )

    # 2. RN01 Critério 1: DOI Inexistente (404) com título também ausente (<85% ou sem autores compatíveis) -> ALUCINADA
    if metrics.doi_status == "INEXISTENTE_404" and (
        metrics.similaridade_titulo_pct < 85.0
        or metrics.correspondencia_autoria == "SEM_INTERSECAO"
    ):
        return (
            VerdictStatus.ALUCINADA,
            HallucinationCategory.DOI_FABRICATION,
            "Remover a referência do artigo ou substituir por uma fonte real verificada.",
        )

    # 3. RN05: Exceções de Escopo (normas ISO/ABNT, legislação, sites web, monografias/livros locais)
    # Se não houver correspondência forte confirmada com autoria compatível, classifica para Revisão Manual (RN05)
    if metrics.excecao_escopo_rn05 and (
        metrics.similaridade_titulo_pct < 85.0
        or metrics.correspondencia_autoria == "SEM_INTERSECAO"
    ):
        return (
            VerdictStatus.SUSPEITA,
            HallucinationCategory.UNVERIFIABLE_GREY_LITERATURE,
            "Verificar manualmente o trecho extraído ou corrigir pequenos erros de metadados.",
        )

    # 4. Caso 1 de Alucinação (Fantasma / Ghost Reference):
    # - Similaridade < 60% em todas as bases, OU
    # - Similaridade parcial (60% a 84%) porém 0% de interseção nos autores (mero ruído lexical na busca)
    if metrics.similaridade_titulo_pct < 60.0 or (
        metrics.similaridade_titulo_pct < 85.0
        and metrics.correspondencia_autoria == "SEM_INTERSECAO"
    ):
        return (
            VerdictStatus.ALUCINADA,
            HallucinationCategory.GHOST_REFERENCE,
            "Remover a referência do artigo ou substituir por uma fonte real verificada.",
        )

    # 5. Caso 2 de Alucinação (Quimera / Atribuição Falsa):
    # Título confirmado (>= 85%), mas 0% de interseção nos sobrenomes dos autores (RN03)
    if metrics.correspondencia_autoria == "SEM_INTERSECAO":
        return (
            VerdictStatus.ALUCINADA,
            HallucinationCategory.CHIMERA,
            "Remover a referência do artigo ou substituir por uma fonte real verificada.",
        )

    # 6. Se o DOI informado retornou 404 mas o título (>=85%) e os autores reais existem na busca textual
    if metrics.doi_status == "INEXISTENTE_404":
        return (
            VerdictStatus.SUSPEITA,
            HallucinationCategory.DOI_FABRICATION,
            "A obra existe, mas o DOI citado retorna 404. Corrigir ou remover o DOI inválido.",
        )

    # 7. Título entre 60% e 84.99% com autores compatíveis (ALTA ou PARCIAL) -> SUSPEITA (Revisar)
    if 60.0 <= metrics.similaridade_titulo_pct < 85.0:
        return (
            VerdictStatus.SUSPEITA,
            HallucinationCategory.PARTIAL_TITLE_OR_METADATA,
            "Verificar manualmente o trecho extraído ou corrigir pequenos erros de metadados.",
        )

    # 8. Título >= 85%, mas ano diverge em mais de 2 anos (RN04) -> SUSPEITA (Revisar)
    if metrics.ano_aceitavel is False:
        return (
            VerdictStatus.SUSPEITA,
            HallucinationCategory.VENUE_OR_YEAR_DISTORTION,
            "Verificar manualmente o trecho extraído ou corrigir pequenos erros de metadados.",
        )

    # 9. Título >= 85%, mas correspondência de autoria apenas PARCIAL (RN03) -> SUSPEITA (Revisar)
    if metrics.correspondencia_autoria == "PARCIAL":
        return (
            VerdictStatus.SUSPEITA,
            HallucinationCategory.PARTIAL_TITLE_OR_METADATA,
            "Verificar manualmente a lista de autores (divergência no primeiro autor ou omissão de coautores).",
        )

    if metrics.doi_informado and not metrics.doi_resolvido:
        return (
            VerdictStatus.SUSPEITA,
            HallucinationCategory.CONSULTA_INCONCLUSIVA,
            "Não foi possível confirmar o DOI. Repita a consulta ou verifique o registro manualmente.",
        )

    # 10. Condição de VÁLIDA: Título >= 85% E Autoria ALTA E (DOI válido ou ausente) E diferença de ano <= 2
    return (
        VerdictStatus.VALIDA,
        HallucinationCategory.NONE,
        "Nenhuma ação necessária. Referência íntegra.",
    )
