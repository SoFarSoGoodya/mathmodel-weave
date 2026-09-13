"""Build publication-ready TeX/PDF packages from frozen modeling results."""

from .errors import MissingAIFacts, PublicationError, ScienceRevisionRequired
from .ai_usage import collect_ai_usage
from .checks import record_visual_review
from .cli import add_publication_parser
from .manifest import classify_manifest_change, generate_results_tex
from .pipeline import build_publication

__all__ = [
    "MissingAIFacts",
    "PublicationError",
    "ScienceRevisionRequired",
    "add_publication_parser",
    "build_publication",
    "classify_manifest_change",
    "collect_ai_usage",
    "generate_results_tex",
    "record_visual_review",
]
