"""Internal helpers for optional CLI progress reporting."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from .progress import WarningQueryProgress

_progress_callback: ContextVar[WarningQueryProgress | None] = ContextVar(
    'progress_callback',
    default=None,
)


@contextmanager
def bind_progress_callback(callback: WarningQueryProgress | None):
    """Bind a progress callback for the current execution context.

    Parameters
    ----------
    callback : ProgressCallback | None
        Progress callback to bind for the current context. Pass ``None`` to
        clear any existing binding within the nested scope.

    Yields
    ------
    None
        A context in which the supplied callback is active.

    """
    token = _progress_callback.set(callback)
    try:
        yield
    finally:
        _progress_callback.reset(token)


def emit_progress(event: str, **payload: Any) -> None:
    """Send a progress event to the active callback, if any.

    Parameters
    ----------
    event : str
        Event name to emit.
    **payload : Any
        Event payload associated with the progress update.

    Returns
    -------
    None
        This function returns nothing. If no callback is currently bound, the
        event is ignored.

    """
    callback = _progress_callback.get()
    if callback is None:
        return
    try:
        callback(event, payload)
    except Exception:
        # Progress is advisory. A UI update must not affect the query result.
        return
