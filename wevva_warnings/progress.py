"""Public types for warning-query progress reporting."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeAlias

WarningQueryProgress: TypeAlias = Callable[[str, dict[str, Any]], None]
"""Callback invoked synchronously with a warning-query progress event."""
