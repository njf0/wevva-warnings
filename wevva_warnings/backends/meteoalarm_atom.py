"""Backend for Meteoalarm Atom feeds with linked CAP alerts."""

from __future__ import annotations

import logging
from urllib.parse import urljoin
from xml.etree import ElementTree

from .._debug import emit_progress
from ..cap import parse_cap_alert
from ..models import Alert
from ..sources import WarningSource
from .base import BackendError, WarningBackend, fetch_text


class MeteoAlarmAtomBackend(WarningBackend):
    """Fetch alerts from Meteoalarm Atom feeds."""

    backend_id = 'meteoalarm_atom'

    def fetch_alerts(
        self,
        source: WarningSource,
        *,
        lat: float | None = None,
        lon: float | None = None,
        lang: str | None = None,
        debug: bool = False,
    ) -> list[Alert]:
        """Fetch alerts for a Meteoalarm Atom source.

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
            Alerts parsed from the linked CAP documents in the Atom feed.

        """
        del lat, lon
        if not source.url:
            return []

        try:
            payload = fetch_text(
                source.url,
                headers={'Accept': '*/*'},
                debug=debug,
            )
        except BackendError:
            return []

        try:
            root = ElementTree.fromstring(payload)
        except ElementTree.ParseError:
            return []

        alert_urls = _cap_urls_from_feed(root, base_url=source.url)
        if not alert_urls:
            return []

        alert_urls = list(dict.fromkeys(alert_urls))
        if debug:
            logging.info('Provider %r found %s CAP documents.', source.id, len(alert_urls))
            emit_progress('documents_total', source=source.id, total=len(alert_urls))

        preferred_lang = lang or source.lang
        alerts: list[Alert] = []
        seen: set[tuple[str, str]] = set()
        for alert_url in alert_urls:
            try:
                alert_payload = fetch_text(alert_url, headers={'Accept': '*/*'}, debug=debug)
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


def _cap_urls_from_feed(root: ElementTree.Element, *, base_url: str) -> list[str]:
    """Extract linked CAP URLs from a Meteoalarm Atom feed.

    Parameters
    ----------
    root : ElementTree.Element
        Root XML element of the Atom feed.
    base_url : str
        Base URL used to resolve relative links.

    Returns
    -------
    list[str]
        CAP document URLs referenced by the feed.

    """
    urls: list[str] = []
    for entry in root.iter():
        if _local_name(entry.tag) != 'entry':
            continue
        for link in entry:
            if _local_name(link.tag) != 'link':
                continue
            if (link.attrib.get('type') or '').lower() != 'application/cap+xml':
                continue
            href = (link.attrib.get('href') or '').strip()
            if href:
                urls.append(urljoin(base_url, href))
    return urls


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
