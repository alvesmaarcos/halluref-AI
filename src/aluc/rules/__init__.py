"""Regras de negócio (RN01 a RN05) e cálculos de similaridade e autoria."""

from .metrics import (
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

__all__ = [
    "normalize_text",
    "calculate_title_similarity",
    "classify_title_similarity",
    "extract_surname",
    "evaluate_author_intersection",
    "evaluate_year_tolerance",
    "evaluate_scope_exception_rn05",
    "compute_comparison_metrics",
    "evaluate_decision_matrix",
]
