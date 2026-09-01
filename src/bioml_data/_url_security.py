"""Shared URL sanitization for user-visible diagnostics."""

import httpx2


def redact_url(source_uri: str) -> str:
    """Remove credentials and query parameters from one URL."""
    return str(
        httpx2.URL(source_uri).copy_with(
            username=None,
            password=None,
            query=None,
        )
    )


__all__ = ["redact_url"]
