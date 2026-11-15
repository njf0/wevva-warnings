"""Shared backend interface and HTTP helpers."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from abc import ABC, abstractmethod
from collections import OrderedDict
from datetime import datetime
from http.cookiejar import CookieJar
from importlib.metadata import PackageNotFoundError, version
from threading import RLock
from typing import TYPE_CHECKING, Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen

from ..models import Alert

if TYPE_CHECKING:
    from ..models import TropicalProduct, TropicalSystem
    from ..sources import WarningSource

DEFAULT_TIMEOUT = 180
try:
    PACKAGE_VERSION = version('wevva-warnings')
except PackageNotFoundError:
    PACKAGE_VERSION = '0.3.0'
DEFAULT_USER_AGENT = f'wevva-warnings/{PACKAGE_VERSION}'


class BackendError(RuntimeError):
    """Raised when a backend request or decode step fails."""


class ETagCachingSession:
    """Small cookie-aware in-process text cache for ETag endpoints.

    The session stores a bounded set of response bodies with their ETags,
    sends ``If-None-Match`` on later requests, and returns the cached body for
    ``304 Not Modified``.  Cookies are retained because some official feeds
    expose linked resources only within the anonymous session established by
    the document request.
    """

    def __init__(self, *, max_entries: int = 2048) -> None:
        """Create an empty bounded cache and cookie-aware opener."""
        if max_entries < 1:
            raise ValueError('max_entries must be positive')
        self._max_entries = max_entries
        self._cache: OrderedDict[str, tuple[str, str]] = OrderedDict()
        self._opener = build_opener(HTTPCookieProcessor(CookieJar()))
        self._lock = RLock()

    def clear(self) -> None:
        """Clear cached response bodies and ETags."""
        with self._lock:
            self._cache.clear()

    def fetch_text(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        debug: bool = False,
    ) -> str:
        """Fetch text while honouring an endpoint's ETag contract."""
        with self._lock:
            cached = self._cache.get(url)
            request_headers = {'User-Agent': DEFAULT_USER_AGENT, **(headers or {})}
            if cached is not None:
                request_headers['If-None-Match'] = cached[0]

            request = Request(url, headers=request_headers)
            try:
                with self._opener.open(request, timeout=timeout) as response:
                    payload = response.read()
                    encoding = response.headers.get_content_charset() or 'utf-8'
                    etag = response.headers.get('ETag')
            except HTTPError as exc:
                if exc.code == 304 and cached is not None:
                    self._cache.move_to_end(url)
                    return cached[1]
                if debug:
                    logging.error('Fetch failed for %r: %s', url, exc)  # noqa: TRY400
                raise BackendError(str(exc)) from exc
            except (URLError, OSError, TimeoutError) as exc:
                if debug:
                    logging.error('Fetch failed for %r: %s', url, exc)  # noqa: TRY400
                raise BackendError(str(exc)) from exc

            text = payload.decode(encoding, errors='replace')
            if etag:
                self._cache[url] = (etag, text)
                self._cache.move_to_end(url)
                while len(self._cache) > self._max_entries:
                    self._cache.popitem(last=False)
            else:
                self._cache.pop(url, None)
            return text


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

    def fetch_tropical_systems(
        self,
        source: WarningSource,
        *,
        lat: float | None = None,
        lon: float | None = None,
        lang: str | None = None,
        debug: bool = False,
        strict: bool = False,
    ) -> list[TropicalSystem]:
        """Return tropical systems for a source.

        Backends that do not publish storm-centric tropical system products can
        keep the default empty implementation.
        """
        if strict:
            raise BackendError(f'Tropical discovery is not implemented for {source.id}')
        del source, lat, lon, lang, debug
        return []

    def fetch_tropical_products(
        self,
        source: WarningSource,
        system: TropicalSystem,
        *,
        debug: bool = False,
    ) -> list[TropicalProduct]:
        """Return lazy supplementary products for one tropical observation.

        Supplementary products are optional.  Backends without reliable
        storm-specific enrichment keep this default empty implementation.
        """
        del source, system, debug
        return []

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
    except HTTPError as exc:
        if debug:
            logging.error('Fetch failed for %r: %s', request_url, exc)  # noqa: TRY400
        raise BackendError(str(exc)) from exc
    except (URLError, OSError, TimeoutError) as exc:
        fallback_payload = _fetch_text_with_curl(
            request_url,
            headers=headers,
            timeout=timeout,
            debug=debug,
        )
        if fallback_payload is not None:
            return fallback_payload
        if debug:
            logging.error('Fetch failed for %r: %s', request_url, exc)  # noqa: TRY400
        raise BackendError(str(exc)) from exc

    return payload.decode(encoding, errors='replace')


def fetch_bytes(
    url: str,
    *,
    params: dict[str, object] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    debug: bool = False,
) -> bytes:
    """Fetch a binary response."""
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
            return response.read()
    except HTTPError as exc:
        if debug:
            logging.error('Fetch failed for %r: %s', request_url, exc)  # noqa: TRY400
        raise BackendError(str(exc)) from exc
    except (URLError, OSError, TimeoutError) as exc:
        fallback_payload = _fetch_bytes_with_curl(
            request_url,
            headers=headers,
            timeout=timeout,
            debug=debug,
        )
        if fallback_payload is not None:
            return fallback_payload
        if debug:
            logging.error('Fetch failed for %r: %s', request_url, exc)  # noqa: TRY400
        raise BackendError(str(exc)) from exc


def _fetch_text_with_curl(
    url: str,
    *,
    headers: dict[str, str] | None,
    timeout: float,
    debug: bool,
) -> str | None:
    """Fetch text via curl when urllib networking fails."""
    curl_path = shutil.which('curl')
    if curl_path is None:
        return None

    command = [
        curl_path,
        '-fsSL',
        '--max-time',
        str(max(1, int(timeout))),
        '-A',
        DEFAULT_USER_AGENT,
    ]
    for key, value in (headers or {}).items():
        command.extend(['-H', f'{key}: {value}'])
    command.append(url)

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            check=False,
            timeout=timeout + 5,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        if debug:
            logging.error('curl fallback failed for %r: %s', url, exc)  # noqa: TRY400
        return None

    if completed.returncode != 0:
        if debug:
            stderr = completed.stderr.decode('utf-8', errors='replace').strip()
            logging.error('curl fallback failed for %r: %s', url, stderr or completed.returncode)  # noqa: TRY400
        return None

    return completed.stdout.decode('utf-8', errors='replace')


def _fetch_bytes_with_curl(
    url: str,
    *,
    headers: dict[str, str] | None,
    timeout: float,
    debug: bool,
) -> bytes | None:
    """Fetch bytes via curl when urllib networking fails."""
    curl_path = shutil.which('curl')
    if curl_path is None:
        return None

    command = [
        curl_path,
        '-fsSL',
        '--max-time',
        str(max(1, int(timeout))),
        '-A',
        DEFAULT_USER_AGENT,
    ]
    for key, value in (headers or {}).items():
        command.extend(['-H', f'{key}: {value}'])
    command.append(url)

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            check=False,
            timeout=timeout + 5,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        if debug:
            logging.error('curl fallback failed for %r: %s', url, exc)  # noqa: TRY400
        return None

    if completed.returncode != 0:
        if debug:
            stderr = completed.stderr.decode('utf-8', errors='replace').strip()
            logging.error('curl fallback failed for %r: %s', url, stderr or completed.returncode)  # noqa: TRY400
        return None

    return completed.stdout
