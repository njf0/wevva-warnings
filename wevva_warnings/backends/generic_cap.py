"""Generic backend for CAP RSS and Atom feeds."""

from __future__ import annotations

import logging
from urllib.parse import urljoin
from xml.etree import ElementTree

from .._debug import emit_progress
from ..cap import parse_cap_alert
from ..models import Alert
from ..sources import WarningSource
from .base import BackendError, WarningBackend, fetch_text


class GenericCAPBackend(WarningBackend):
    """Fetch CAP alerts from a generic RSS or Atom feed."""

    backend_id = 'generic_cap'

    def fetch_alerts(
        self,
        source: WarningSource,
        *,
        lat: float | None = None,
        lon: float | None = None,
        lang: str | None = None,
        debug: bool = False,
    ) -> list[Alert]:
        """Fetch alerts for a generic CAP feed source.

        Parameters
        ----------
        source : WarningSource
            Source definition to query.
        lat : float | None, optional
            Unused for this backend. Included for interface compatibility.
        lon : float | None, optional
            Unused for this backend. Included for interface compatibility.
        lang : str | None, optional
            Preferred language code used when selecting CAP ``info`` blocks.
        debug : bool, optional
            If True, emit progress information while fetching alerts.

        Returns
        -------
        list[Alert]
            Alerts parsed from the source feed and any linked CAP documents.

        """
        del lat, lon
        if not source.url:
            return []
        preferred_lang = lang or source.lang

        try:
            payload = fetch_text(
                source.url,
                headers={
                    'Accept': 'application/atom+xml, application/rss+xml, application/xml, text/xml',
                },
                debug=debug,
            )
        except BackendError:
            return []

        try:
            root = ElementTree.fromstring(payload)
        except ElementTree.ParseError:
            return []

        if _local_name(root.tag) == 'alert':
            direct_alert = parse_cap_alert(
                payload,
                source=source.id,
                preferred_lang=preferred_lang,
                url=source.url,
            )
            return [direct_alert] if direct_alert is not None else []

        alerts: list[Alert] = []
        seen_alerts: set[tuple[str, str]] = set()
        for element in root.iter():
            if _local_name(element.tag) != 'alert':
                continue
            xml_payload = ElementTree.tostring(element, encoding='unicode')
            alert = parse_cap_alert(
                xml_payload,
                source=source.id,
                preferred_lang=preferred_lang,
                url=source.url,
            )
            if alert is None:
                continue
            key = (alert.source, alert.id)
            if key in seen_alerts:
                continue
            seen_alerts.add(key)
            alerts.append(alert)

        alert_urls: list[str] = []
        for element in root.iter():
            if _local_name(element.tag) not in {'entry', 'item'}:
                continue
            alert_urls.extend(_urls_from_entry(element, base_url=source.url))

        alert_urls = list(dict.fromkeys(alert_urls))
        if debug:
            logging.info('Provider %r found %s CAP documents.', source.id, len(alert_urls))
            emit_progress('documents_total', source=source.id, total=len(alert_urls))

        for alert_url in alert_urls:
            try:
                alert_payload = fetch_text(
                    alert_url,
                    headers={'Accept': 'application/cap+xml, application/xml, text/xml'},
                    debug=debug,
                )
                alert = parse_cap_alert(
                    alert_payload,
                    source=source.id,
                    preferred_lang=preferred_lang,
                    url=alert_url,
                )
                if alert is None:
                    continue
                key = (alert.source, alert.id)
                if key in seen_alerts:
                    continue
                seen_alerts.add(key)
                alerts.append(alert)
            except BackendError:
                continue
            finally:
                if debug:
                    emit_progress('documents_advance', source=source.id)
        return alerts


def _urls_from_entry(entry: ElementTree.Element, *, base_url: str) -> list[str]:
    """Extract candidate CAP URLs from one RSS or Atom entry.

    Parameters
    ----------
    entry : ElementTree.Element
        RSS ``item`` or Atom ``entry`` element to inspect.
    base_url : str
        Base URL used to resolve relative links.

    Returns
    -------
    list[str]
        Preferred CAP URLs when any are found, otherwise fallback URLs from the
        entry.

    """
    preferred: list[str] = []
    fallback: list[str] = []

    for element in entry.iter():
        tag_name = _local_name(element.tag)
        href = element.attrib.get('href') or element.attrib.get('src')
        link_type = (element.attrib.get('type') or '').lower()
        rel = (element.attrib.get('rel') or '').lower()

        if href:
            url = urljoin(base_url, href.strip())
            if _looks_like_cap_link(url, link_type=link_type, rel=rel):
                preferred.append(url)
            elif _looks_like_url(url):
                fallback.append(url)

        text = (element.text or '').strip()
        if text and _looks_like_url(text):
            url = urljoin(base_url, text)
            if _looks_like_cap_link(url, link_type=link_type, rel=rel or tag_name):
                preferred.append(url)
            else:
                fallback.append(url)

    return preferred or fallback


def _looks_like_cap_link(url: str, *, link_type: str, rel: str) -> bool:
    """Return whether a link appears to reference a CAP document.

    Parameters
    ----------
    url : str
        URL to inspect.
    link_type : str
        Link MIME type, if declared.
    rel : str
        Link relation, if declared.

    Returns
    -------
    bool
        ``True`` if the link looks like a CAP document, otherwise ``False``.

    """
    lowered = url.lower()
    if 'cap' in link_type or 'xml' in link_type:
        return True
    if 'cap' in lowered or lowered.endswith('.xml'):
        return True
    return rel in {'enclosure', 'related'} and _looks_like_url(url)


def _looks_like_url(value: str) -> bool:
    """Return whether a string looks like a URL or absolute path.

    Parameters
    ----------
    value : str
        String to inspect.

    Returns
    -------
    bool
        ``True`` if the value looks like a URL or root-relative path,
        otherwise ``False``.

    """
    lowered = value.lower()
    return lowered.startswith('http://') or lowered.startswith('https://') or lowered.startswith('/')


def _local_name(tag: str) -> str:
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
