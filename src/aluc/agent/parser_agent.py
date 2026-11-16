"""Parser Semântico via LLM (RF03 e RNF03) usando Gemini 3.8 Flash e Structured Output."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional
from google import genai

from aluc.config import AlucConfig
from aluc.ingestion.bib_extractor import parse_bibtex_entries_deterministic
from aluc.schemas import ParsedReference, ReferenceType

PARSER_SYSTEM_INSTRUCTION = """Você é um Parser Bibliográfico Acadêmico de alta precisão (RF03).
Sua única tarefa é transformar um bloco bruto de referências bibliográficas (extraído de PDF, LaTeX ou BibTeX)
em uma lista JSON estruturada.

Regras estritas:
1. Extraia CADA referência individualmente sem omitir nenhuma e sem inventar dados que não estejam no trecho original.
2. Para cada referência, preencha:
   - `texto_original`: o trecho literal exato da referência.
   - `titulo`: apenas o título da obra (sem nomes de autores, sem ano e sem nome da revista/conferência).
   - `autores`: lista de strings, um autor por item (ex: ["Vaswani, Ashish", "Shazeer, Noam"]).
   - `ano`: ano de publicação como inteiro de 4 dígitos (ex: 2017) ou null se ausente.
   - `veiculo`: nome do periódico, conferência, editora ou instituição, ou null.
   - `doi`: apenas o código DOI no padrão "10.xxxx/yyyy" (sem prefixo https://doi.org/), ou null se ausente.
   - `url`: URL completa caso citada na referência, ou null.
   - `tipo_inferido`: classifique entre "article", "conference", "preprint", "book", "thesis", "standard" (normas ABNT/ISO/IEEE), "legislation" (leis/decretos), "webpage" (sites/@misc) ou "techreport".
"""

PARSED_REFERENCES_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "referencias": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "texto_original": {"type": "string"},
                    "titulo": {"type": "string"},
                    "autores": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "ano": {"type": ["integer", "null"]},
                    "veiculo": {"type": ["string", "null"]},
                    "doi": {"type": ["string", "null"]},
                    "url": {"type": ["string", "null"]},
                    "tipo_inferido": {
                        "type": "string",
                        "enum": [t.value for t in ReferenceType],
                    },
                },
                "required": [
                    "texto_original",
                    "titulo",
                    "autores",
                    "ano",
                    "veiculo",
                    "doi",
                    "url",
                    "tipo_inferido",
                ],
            },
        }
    },
    "required": ["referencias"],
}


def _heuristic_parse_plain_references(raw_block: str) -> List[ParsedReference]:
    """Parser heurístico local de contingência (para LaTeX \\bibitem ou linhas numeradas de PDF)
    utilizado caso o arquivo seja processado sem chave de API ou como pré-segmentador.
    """
    if not raw_block or not raw_block.strip():
        return []

    # Caso seja BibTeX (@article, @book, @misc...)
    if re.search(r"(?m)^\s*@[a-zA-Z]+\s*\{", raw_block):
        bib_parsed = parse_bibtex_entries_deterministic(raw_block)
        if bib_parsed:
            return bib_parsed

    # Caso contenha \bibitem (LaTeX)
    if "\\bibitem" in raw_block:
        parts = re.split(r"(?=\\bibitem(?:\[[^\]]*\])?\{[^}]+\})", raw_block)
        entries = [
            p.strip()
            for p in parts
            if p.strip() and "\\bibitem" in p
        ]
    else:
        # Divide por numeração [1], 1., ou parágrafos duplos
        numbered = re.split(r"(?m)(?=^\s*(?:\[\d+\]|\d+\.\s+))", raw_block.strip())
        if len([x for x in numbered if x.strip()]) > 1:
            entries = [x.strip() for x in numbered if x.strip()]
        else:
            entries = [
                p.strip()
                for p in re.split(r"\n\s*\n", raw_block.strip())
                if len(p.strip()) > 20
            ]

    results: List[ParsedReference] = []
    for entry in entries:
        clean_entry = re.sub(r"\\bibitem(?:\[[^\]]*\])?\{[^}]+\}", "", entry)
        clean_entry = re.sub(r"\\end\{thebibliography\}", "", clean_entry)
        clean_entry = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", clean_entry)
        clean_entry = re.sub(r"\s+", " ", clean_entry).strip()
        if not clean_entry:
            continue

        doi_match = re.search(r"(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)", clean_entry)
        doi = doi_match.group(1).rstrip(".") if doi_match else None

        url_match = re.search(r"(https?://[^\s,;\)]+)", clean_entry)
        url = url_match.group(1).rstrip(".") if url_match else None

        year_match = re.search(r"\b(1[89]\d{2}|20\d{2})\b", clean_entry)
        year = int(year_match.group(1)) if year_match else None

        # Tenta extrair título entre aspas ou após o ano/ponto dos autores
        quoted_title = re.search(r'["“``]([^"”\'\']{10,})["”\'\']', clean_entry)
        if quoted_title:
            title = quoted_title.group(1).strip().rstrip(".")
            before_title = clean_entry[: quoted_title.start()].strip()
            after_title = clean_entry[quoted_title.end() :].strip()
        else:
            # Divide por pontos: [0] = autores (ou autores + ano), [1] = título, [2] = veículo
            segments = [
                s.strip()
                for s in re.split(r"\.\s+", re.sub(r"^\[\d+\]\s*|^\d+\.\s*", "", clean_entry))
                if s.strip()
            ]
            if len(segments) >= 2:
                before_title = segments[0]
                # Se o segundo segmento for apenas o ano (ex: "(2020)"), o título está no terceiro
                if re.fullmatch(r"\(?\d{4}[a-z]?\)?", segments[1]) and len(segments) >= 3:
                    title = segments[2]
                    after_title = ". ".join(segments[3:])
                else:
                    title = segments[1]
                    after_title = ". ".join(segments[2:])
            else:
                before_title = ""
                title = clean_entry
                after_title = ""

        # Limpa prefixo numérico e ano do bloco de autores
        before_title = re.sub(r"^\[\d+\]\s*|^\d+\.\s*", "", before_title)
        before_title = re.sub(r"\(\s*\d{4}[a-z]?\s*\)\.?", "", before_title).strip().rstrip(".,:")
        authors = [
            a.strip()
            for a in re.split(r";|\s+and\s+|\s+e\s+|,\s+(?=[A-Z][a-z]+\s+[A-Z])", before_title)
            if a.strip() and not re.fullmatch(r"\d{4}", a.strip())
        ]

        venue = after_title.split(".")[0].strip() if after_title else None

        results.append(
            ParsedReference(
                texto_original=entry.strip(),
                titulo=title.strip().rstrip("."),
                autores=authors,
                ano=year,
                veiculo=venue,
                doi=doi,
                url=url,
                tipo_inferido=ReferenceType.ARTICLE,
            )
        )

    return results


class SemanticReferenceParser:
    """Agente de estruturação semântica (RF03) usando Gemini 3.8 Flash via Interactions API."""

    def __init__(self, config: Optional[AlucConfig] = None) -> None:
        self.config = config or AlucConfig.from_env()
        self.client: Optional[genai.Client] = None
        if self.config.gemini_api_key:
            self.client = genai.Client(api_key=self.config.gemini_api_key)

    def parse_references(
        self, raw_references_block: str, source_format: str = "PDF"
    ) -> List[ParsedReference]:
        """Estrutura o bloco bruto de referências em uma lista de objetos ParsedReference (RF03)."""
        if not raw_references_block or not raw_references_block.strip():
            return []

        # Se for arquivo .bib bem formado e não houver necessidade de fallback ou se o cliente LLM não estiver configurado
        if source_format.upper() == "BIB" and not self.client:
            return parse_bibtex_entries_deterministic(raw_references_block)

        if not self.client:
            return _heuristic_parse_plain_references(raw_references_block)

        try:
            prompt = (
                f"Formato de origem: {source_format}\n\n"
                "Extraia todas as referências bibliográficas do bloco abaixo para o formato JSON padronizado:\n\n"
                f"```\n{raw_references_block}\n```"
            )
            interaction = self.client.interactions.create(
                model=self.config.gemini_model,
                system_instruction=PARSER_SYSTEM_INSTRUCTION,
                input=prompt,
                response_format=PARSED_REFERENCES_JSON_SCHEMA,
                response_mime_type="application/json",
                generation_config={
                    "seed": self.config.seed,
                    "thinking_level": self.config.thinking_level,
                },
            )
            output_text = interaction.output_text or ""
            data = json.loads(output_text)
            refs_raw = data.get("referencias") or []
            parsed = [ParsedReference.model_validate(item) for item in refs_raw]
            if parsed:
                return parsed
        except Exception:
            # Em caso de falha de rede/cota na etapa de parsing, utiliza o extrator determinístico local
            pass

        if source_format.upper() == "BIB":
            bib_refs = parse_bibtex_entries_deterministic(raw_references_block)
            if bib_refs:
                return bib_refs
        return _heuristic_parse_plain_references(raw_references_block)
