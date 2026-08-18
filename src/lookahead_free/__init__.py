"""Verifiable look-ahead-freedom for the value-independent fragment.

Grounding: Fonseca (2026), "Look-Ahead-Freedom as Temporal Non-Interference"
(arXiv:2607.04958) proves look-ahead-freedom is undecidable in general
(pi-0-1-hard when availability depends on data values), but admits a
linear-time decidable type-effect system on the *value-independent
fragment* — windowing, resampling, joins, point-in-time and vintage reads,
agentic retrieval.

This tool implements exactly that fragment as a declarative pipeline DAG
with temporal annotations, and checks it exactly.  Operations declared
value-dependent are not silently trusted: they are flagged at the
heuristic boundary (P1), because for them no verifiable claim exists.
"""

from .checks import check_pipeline
from .model import Pipeline, load_pipeline

__version__ = "0.1.0"

__all__ = ["Pipeline", "check_pipeline", "load_pipeline"]
