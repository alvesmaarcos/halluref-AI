"""Configurações globais, variáveis de ambiente e parâmetros de Rate Limiting."""

from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class AlucConfig:
    """Configuração central do Agente ALUC."""

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"
    seed: int = 0
    thinking_level: str = "low"
    # Intervalo mínimo entre requisições por provedor (em segundos)
    crossref_min_interval_sec: float = 0.25
    openalex_min_interval_sec: float = 0.25
    semantic_scholar_min_interval_sec: float = 1.0
    http_timeout_sec: float = 15.0

    @classmethod
    def from_env(
        cls,
        api_key_override: str | None = None,
        model_override: str | None = None,
    ) -> "AlucConfig":
        """Carrega a configuração a partir do ambiente com suporte a sobrescrita via UI/CLI."""
        api_key = (
            api_key_override
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
            or ""
        ).strip()
        model = (
            model_override
            or os.getenv("ALUC_GEMINI_MODEL")
            or "gemini-3.8-flash"
        ).strip()
        return cls(
            gemini_api_key=api_key,
            gemini_model=model,
        )

    @property
    def user_agent(self) -> str:
        """Retorna o cabeçalho User-Agent da aplicação."""
        return "AlucAuditAgent/1.0 (https://github.com/ufc-pibiti/aluc)"
