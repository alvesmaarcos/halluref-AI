"""Agente de IA para parsing semântico (RF03) e auditoria via Tool-Calling (RF04, RF05)."""

from .auditor_agent import BibliographicAuditorAgent
from .parser_agent import SemanticReferenceParser
from .tools import AGENT_TOOL_DECLARATIONS, ReferenceAuditToolkit

__all__ = [
    "SemanticReferenceParser",
    "ReferenceAuditToolkit",
    "AGENT_TOOL_DECLARATIONS",
    "BibliographicAuditorAgent",
]
