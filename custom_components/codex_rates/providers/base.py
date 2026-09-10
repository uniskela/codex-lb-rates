"""Provider protocol for Codex Rates."""

from __future__ import annotations

from typing import Protocol

from ..models import ProviderSnapshot


class QuotaProvider(Protocol):
    """Async provider that returns a quota snapshot."""

    async def async_fetch(self) -> ProviderSnapshot:
        """Fetch current account quotas."""

    async def async_close(self) -> None:
        """Release any held resources."""
