"""Configuration shared by native SDK input handling and trusted URL consent."""

from __future__ import annotations

from collections.abc import Sequence

from clio_agent import conf


def trusted_origins(explicit: Sequence[str] | None = None) -> tuple[str, ...]:
    """Resolve the existing explicit URL allow-list without fetching or granting it."""
    if explicit is not None:
        return tuple(explicit)
    return tuple(
        conf.resolve(
            "tools.mcp.elicitation.url_trusted_origins",
            env="CLIO_MCP_ELICITATION_URL_TRUSTED_ORIGINS",
            default=[],
            cast=conf.as_csv,
        )
        or ()
    )
