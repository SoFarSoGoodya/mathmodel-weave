"""Publication-specific failures with actionable ownership boundaries."""


class PublicationError(RuntimeError):
    """The publication request or build is invalid."""


class ScienceRevisionRequired(PublicationError):
    """An input change requires execution/evidence/human-control revision."""


class MissingAIFacts(PublicationError):
    """AI use was recorded but truthful adoption or verification facts are missing."""
