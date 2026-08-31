"""dtdecoder -- decodificador tactico de entrenadores (Fases 0-3)."""

from .absorbing import AbsorbingChain, empirical_start_distribution
from .config import Config
from .eras import (
    attach_coach,
    coverage_report,
    detect_regime_changes,
    load_eras,
    load_match_dates,
    match_coach_table,
    select_units,
    write_template,
)
from .estimate import count_matrix, cv_lambda, error_curve, mle, shrink, sparsity_report
from .grid import StateSpace
from .inference import (
    benjamini_hochberg,
    bootstrap_diff,
    context_contrast,
    tactical_fingerprint,
)
from .possessions import build_transitions, coordinate_sanity

__version__ = "0.6.0"

__all__ = [
    "AbsorbingChain",
    "Config",
    "StateSpace",
    "attach_coach",
    "benjamini_hochberg",
    "bootstrap_diff",
    "build_transitions",
    "context_contrast",
    "coordinate_sanity",
    "count_matrix",
    "coverage_report",
    "cv_lambda",
    "detect_regime_changes",
    "empirical_start_distribution",
    "error_curve",
    "load_eras",
    "load_match_dates",
    "match_coach_table",
    "mle",
    "select_units",
    "shrink",
    "sparsity_report",
    "tactical_fingerprint",
    "write_template",
]
