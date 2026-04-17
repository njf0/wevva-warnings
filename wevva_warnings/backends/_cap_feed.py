"""Shared helpers for providers that fetch linked CAP documents from feeds."""

from __future__ import annotations

import logging
from urllib.parse import urljoin
from xml.etree import ElementTree

from .._debug import emit_progress
from ..cap import parse_cap_alert
from ..models import Alert
from ..sources import WarningSource
from .base import BackendError, fetch_text

FEED_ACCEPT = 'application/rss+xml, application/atom+xml, application/xml, text/xml'
CAP_ACCEPT = 'application/cap+xml, application/xml, text/xml'


def fetch_feed_root(
    source: WarningSource,
    *,
    debug: bool = False,
    headers: dict[str, str] | None = None,
) -> ElementTree.Element | None:
    """Fetch and parse one feed XML document.

    Parameters
    ----------
    source : WarningSource
        Source definition whose feed should be fetched.
    debug : bool, optional
        If True, log fetch failures via the shared HTTP helper.
    headers : dict[str, str] | None, optional
        Additional request headers.

    Returns
    -------
    ElementTree.Element | None
        Parsed root element if the feed can be fetched and parsed, otherwise
        ``None``.

    """
    if not source.url:
        return None

    try:
        payload = fetch_text(source.url, headers=headers or {'Accept': FEED_ACCEPT}, debug=debug)
    except BackendError:
        return None

    try:
        return ElementTree.fromstring(payload)
    except ElementTree.ParseError:
        return None


def fetch_cap_documents(
    source: WarningSource,
    alert_urls: list[str],
    *,
    preferred_lang: str | None = None,
    debug: bool = False,
    headers: dict[str, str] | None = None,
) -> list[Alert]:
    """Fetch CAP documents and parse them into alerts.

    Parameters
    ----------
    source : WarningSource
        Source definition whose CAP documents are being fetched.
    alert_urls : list[str]
        CAP document URLs to fetch.
    preferred_lang : str | None, optional
        Preferred language code used when selecting CAP ``info`` blocks.
    debug : bool, optional
        If True, emit progress information while fetching CAP documents.
    headers : dict[str, str] | None, optional
        Additional request headers for CAP document fetches.

    Returns
    -------
    list[Alert]
        Alerts parsed from the supplied CAP document URLs.

    """
    urls = list(dict.fromkeys(alert_urls))
    if debug:
        logging.info('Provider %r found %s CAP documents.', source.id, len(urls))
        emit_progress('documents_total', source=source.id, total=len(urls))

    alerts: list[Alert] = []
    seen: set[tuple[str, str]] = set()
    for alert_url in urls:
        try:
            alert_payload = fetch_text(alert_url, headers=headers or {'Accept': CAP_ACCEPT}, debug=debug)
            alert = parse_cap_alert(
                alert_payload,
                source=source.id,
                preferred_lang=preferred_lang,
                url=alert_url,
            )
            if alert is None:
                continue
            key = (alert.source, alert.id)
            if key in seen:
                continue
            seen.add(key)
            alerts.append(alert)
        except BackendError:
            continue
        finally:
            if debug:
                emit_progress('documents_advance', source=source.id)

    return alerts


def local_name(tag: str) -> str:
    """Return the local name for a possibly namespaced XML tag.

    Parameters
    ----------
    tag : str
        XML tag, optionally in ``{namespace}name`` form.

    Returns
    -------
    str
        Tag name without any namespace prefix.

    """
    return tag.split('}')[-1]


def child_text(element: ElementTree.Element, name: str) -> str | None:
    """Return the trimmed text for the first direct child with a given name.

    Parameters
    ----------
    element : ElementTree.Element
        Parent XML element to inspect.
    name : str
        Local child tag name to match.

    Returns
    -------
    str | None
        Trimmed child text if found, otherwise ``None``.

    """
    for child in element:
        if local_name(child.tag) != name:
            continue
        text = (child.text or '').strip()
        return text or None
    return None


def absolute_url(base_url: str, value: str | None) -> str | None:
    """Resolve a URL-like value relative to a feed URL.

    Parameters
    ----------
    base_url : str
        Base URL used to resolve relative links.
    value : str | None
        Candidate URL value.

    Returns
    -------
    str | None
        Absolute URL if the value looks usable, otherwise ``None``.

    """
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    if text.startswith(('http://', 'https://', '/')):
        return urljoin(base_url, text)
    return None
