"""Normalized weather alert model."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

Geometry = dict[str, Any]


@dataclass(slots=True)
class Alert:
    """Represent one normalized weather alert."""

    id: str
    source: str
    event: str
    headline: str
    url: str | None = None
    severity: str | None = None
    urgency: str | None = None
    certainty: str | None = None
    description: str | None = None
    instruction: str | None = None
    onset: datetime | None = None
    expires: datetime | None = None
    areas: list[str] = field(default_factory=list)
    geometry: Geometry | None = None

    def is_active(self, now: datetime | None = None) -> bool:
        """Return whether the alert is currently active.

        Parameters
        ----------
        now : datetime | None, optional
            Time to compare the alert against. If not provided, the current UTC
            time will be used.

        Returns
        -------
        bool
            ``True`` if the alert has started and has not yet expired,
            otherwise ``False``.

        """
        if now is None:
            now = datetime.now(UTC)
        elif now.tzinfo is None:
            now = now.replace(tzinfo=UTC)
        else:
            now = now.astimezone(UTC)

        onset = self.onset
        if onset is not None:
            if onset.tzinfo is None:
                onset = onset.replace(tzinfo=UTC)
            else:
                onset = onset.astimezone(UTC)
            if now < onset:
                return False

        expires = self.expires
        if expires is not None:
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=UTC)
            else:
                expires = expires.astimezone(UTC)
            if now > expires:
                return False

        return True
