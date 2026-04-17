"""Provider backend for Sierra Leone Meteorological Agency CAP feeds."""

from __future__ import annotations

import re
from xml.etree import ElementTree

from ..cap import parse_cap_alert
from ..models import Alert
from ..sources import WarningSource
from ._cap_feed import absolute_url, child_text, fetch_feed_root, local_name
from .base import BackendError, WarningBackend, fetch_text


class SLMETBackend(WarningBackend):
    """Fetch alerts from Sierra Leone CAP feeds."""

    backend_id = 'slmet'

    def fetch_alerts(
        self,
        source: WarningSource,
        *,
        lat: float | None = None,
        lon: float | None = None,
        lang: str | None = None,
        debug: bool = False,
    ) -> list[Alert]:
        """Fetch alerts for a Sierra Leone CAP source.

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
            Alerts parsed from linked Sierra Leone CAP documents.

        """
        del lat, lon
        root = fetch_feed_root(source, debug=debug)
        if root is None or not source.url:
            return []

        urls = _slmet_alert_urls(root, base_url=source.url)
        alerts: list[Alert] = []
        seen: set[tuple[str, str]] = set()

        for alert_url in urls:
            try:
                alert_payload = fetch_text(
                    alert_url,
                    headers={'Accept': 'application/cap+xml, application/xml, text/xml'},
                    debug=debug,
                )
            except BackendError:
                continue

            alert = parse_cap_alert(
                alert_payload,
                source=source.id,
                preferred_lang=lang or source.lang,
                url=alert_url,
            )
            if alert is None:
                continue

            expanded_area_names = _expand_slmet_area_names(_slmet_area_descs(alert_payload))
            if expanded_area_names:
                alert.area_names = expanded_area_names

            key = (alert.source, alert.id)
            if key in seen:
                continue
            seen.add(key)
            alerts.append(alert)

        return alerts


def _slmet_alert_urls(root: ElementTree.Element, *, base_url: str) -> list[str]:
    """Return candidate CAP URLs from a Sierra Leone RSS feed.

    Parameters
    ----------
    root : ElementTree.Element
        Root XML element of the Sierra Leone RSS feed.
    base_url : str
        Base URL used to resolve relative links.

    Returns
    -------
    list[str]
        Linked CAP document URLs discovered in the feed.

    """
    urls: list[str] = []
    for item in root.iter():
        if local_name(item.tag) != 'item':
            continue
        url = absolute_url(base_url, child_text(item, 'link'))
        if url and '/api/cap/' in url.lower() and url.lower().endswith('.xml'):
            urls.append(url)
    return list(dict.fromkeys(urls))


def _slmet_area_descs(xml_payload: str | bytes) -> list[str]:
    """Extract raw Sierra Leone ``areaDesc`` texts from one CAP document.

    Parameters
    ----------
    xml_payload : str | bytes
        CAP XML document to inspect.

    Returns
    -------
    list[str]
        Raw ``areaDesc`` texts found in the document.

    """
    try:
        root = ElementTree.fromstring(xml_payload)
    except ElementTree.ParseError:
        return []

    descriptions: list[str] = []
    for info in root.iter():
        if local_name(info.tag) != 'info':
            continue
        for area in info:
            if local_name(area.tag) != 'area':
                continue
            description = child_text(area, 'areaDesc')
            if description:
                descriptions.append(description)
    return descriptions


def _expand_slmet_area_names(descriptions: list[str]) -> list[str]:
    """Expand Sierra Leone area text into separate area names.

    Parameters
    ----------
    descriptions : list[str]
        Raw ``areaDesc`` texts extracted from CAP.

    Returns
    -------
    list[str]
        Area names split from provider phrasing such as ``A and B``.

    """
    expanded: list[str] = []
    for description in descriptions:
        normalized = re.sub(r'\s+', ' ', description).strip(' .')
        if not normalized:
            continue
        parts = re.split(r'\s+and\s+', normalized, flags=re.IGNORECASE)
        for part in parts:
            cleaned = part.strip(' .')
            if cleaned and cleaned not in expanded:
                expanded.append(cleaned)
    return expanded
