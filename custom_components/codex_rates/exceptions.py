"""Exceptions for Codex Rates."""

from __future__ import annotations


class CodexRatesError(Exception):
    """Base error."""


class CodexRatesAuthError(CodexRatesError):
    """Authentication failed permanently until user reconfigures."""


class CodexRatesApiError(CodexRatesError):
    """Upstream API returned an unexpected error."""
