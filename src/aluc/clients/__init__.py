"""Conectores HTTP para Crossref, OpenAlex, Semantic Scholar e doi.org (RN01, RF04, RNF04)."""

from .crossref import CrossrefClient
from .http_client import PoliteHttpClient
from .openalex import OpenAlexClient
from .semantic_scholar import SemanticScholarClient

__all__ = [
    "PoliteHttpClient",
    "CrossrefClient",
    "OpenAlexClient",
    "SemanticScholarClient",
]
