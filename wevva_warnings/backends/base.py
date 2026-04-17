"""Shared backend interface and HTTP helpers."""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from importlib.metadata import PackageNotFoundError, version
from typing import TYPE_CHECKING, Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ..models import Alert

if TYPE_CHECKING:
    from ..sources import WarningSource

DEFAULT_TIMEOUT = 180
try:
    PACKAGE_VERSION = version('wevva-warnings')
except PackageNotFoundError:
    PACKAGE_VERSION = '0.2.1'
DEFAULT_USER_AGENT = f'wevva-warnings/{PACKAGE_VERSION}'


class BackendError(RuntimeError):
    """Raised when a backend request or decode step fails."""


class WarningBackend(ABC):
    """Define the minimal interface for warning backends."""

    backend_id: str
    uses_native_point_query = False

    @abstractmethod
    def fetch_alerts(
        self,
        source: WarningSource,
        *,
        lat: float | None = None,
        lon: float | None = None,
        lang: str | None = None,
        debug: bool = False,
    ) -> list[Alert]:
        """Return alerts for a source.

        Parameters
        ----------
        source : WarningSource
            Source definition to query.
        lat : float | None, optional
            Latitude used to constrain the query when the backend supports it.
        lon : float | None, optional
            Longitude used to constrain the query when the backend supports it.
        lang : str | None, optional
            Preferred language code for localized fields, if supported by the
            backend.
        debug : bool, optional
            If True, emit progress or debug information while fetching.

        Returns
        -------
        list[Alert]
            Alerts returned by the backend for the requested source.

        """

    @staticmethod
    def text_or_none(value: Any) -> str | None:
        """Return a trimmed string or ``None``.

        Parameters
        ----------
        value : Any
            Value to normalize.

        Returns
        -------
        str | None
            Trimmed string if the input is a non-empty string, otherwise
            ``None``.

        """
        if not isinstance(value, str):
            return None
        text = value.strip()
        return text or None

    @staticmethod
    def parse_datetime(value: Any) -> datetime | None:
        """Parse an ISO-like datetime value.

        Parameters
        ----------
        value : Any
            Value to parse.

        Returns
        -------
        datetime | None
            Parsed datetime if successful, otherwise ``None``.

        """
        text = WarningBackend.text_or_none(value)
        if text is None:
            return None
        if text.endswith('Z'):
            text = f'{text[:-1]}+00:00'
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None

    @staticmethod
    def split_areas(value: Any) -> list[str]:
        """Split an area description into individual names.

        Parameters
        ----------
        value : Any
            Delimited area description to split.

        Returns
        -------
        list[str]
            Trimmed area names extracted from the supplied value.

        """
        text = WarningBackend.text_or_none(value)
        if not text:
            return []
        normalized = text.replace(';', ',')
        return [part.strip() for part in normalized.split(',') if part.strip()]


def fetch_json(
    url: str,
    *,
    params: dict[str, object] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    debug: bool = False,
) -> Any:
    """Fetch and decode a JSON document.

    Parameters
    ----------
    url : str
        URL to fetch.
    params : dict[str, object] | None, optional
        Query parameters to append to the URL.
    headers : dict[str, str] | None, optional
        Additional request headers.
    timeout : float, optional
        Request timeout in seconds.
    debug : bool, optional
        If True, log fetch failures.

    Returns
    -------
    Any
        Decoded JSON payload.

    Raises
    ------
    BackendError
        If the response cannot be fetched or parsed as JSON.

    """
    text = fetch_text(url, params=params, headers=headers, timeout=timeout, debug=debug)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise BackendError('Invalid JSON response') from exc


def fetch_text(
    url: str,
    *,
    params: dict[str, object] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    debug: bool = False,
) -> str:
    """Fetch a text response.

    Parameters
    ----------
    url : str
        URL to fetch.
    params : dict[str, object] | None, optional
        Query parameters to append to the URL.
    headers : dict[str, str] | None, optional
        Additional request headers.
    timeout : float, optional
        Request timeout in seconds.
    debug : bool, optional
        If True, log fetch failures.

    Returns
    -------
    str
        Decoded response body.

    Raises
    ------
    BackendError
        If the response cannot be fetched.

    """
    request_url = url
    if params:
        query = urlencode({key: str(value) for key, value in params.items()})
        separator = '&' if '?' in request_url else '?'
        request_url = f'{request_url}{separator}{query}'

    request = Request(
        request_url,
        headers={'User-Agent': DEFAULT_USER_AGENT, **(headers or {})},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = response.read()
            encoding = response.headers.get_content_charset() or 'utf-8'
    except (HTTPError, URLError, OSError, TimeoutError) as exc:
        if debug:
            logging.error('Fetch failed for %r: %s', request_url, exc)  # noqa: TRY400
        raise BackendError(str(exc)) from exc

    return payload.decode(encoding, errors='replace')
