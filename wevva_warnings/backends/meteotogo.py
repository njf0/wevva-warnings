"""Provider backend for METEO TOGO CAP feeds."""

from __future__ import annotations

import re
from xml.etree import ElementTree

from ..cap import parse_cap_alert
from ..models import Alert
from ..sources import WarningSource
from ._cap_feed import absolute_url, child_text, fetch_feed_root, local_name
from .base import BackendError, WarningBackend, fetch_text

TOGO_REGION_PATTERNS = [
    ('Maritime', re.compile(r'\bMaritime(?:-Nord)?\b', flags=re.IGNORECASE)),
    ('Plateaux', re.compile(r'\bPlateaux\b', flags=re.IGNORECASE)),
    ('Centrale', re.compile(r'\bCentrale\b', flags=re.IGNORECASE)),
    ('Kara', re.compile(r'\bKara\b', flags=re.IGNORECASE)),
    ('Savanes', re.compile(r'\bSavanes\b', flags=re.IGNORECASE)),
]


class MeteoTogoBackend(WarningBackend):
    """Fetch alerts from METEO TOGO CAP feeds."""

    backend_id = 'meteotogo'

    def fetch_alerts(
        self,
        source: WarningSource,
        *,
        lat: float | None = None,
        lon: float | None = None,
        lang: str | None = None,
        debug: bool = False,
    ) -> list[Alert]:
        """Fetch alerts for a Togo CAP source.

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
            Alerts parsed from linked Togo CAP documents.

        """
        del lat, lon
        root = fetch_feed_root(source, debug=debug)
        if root is None or not source.url:
            return []

        urls = _meteotogo_alert_urls(root, base_url=source.url)
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

            area_descs, headlines, descriptions, audiences = _meteotogo_info_texts(alert_payload)
            expanded_area_names = _expand_meteotogo_area_names(area_descs, headlines, descriptions, audiences)
            if expanded_area_names:
                alert.area_names = expanded_area_names

            key = (alert.source, alert.id)
            if key in seen:
                continue
            seen.add(key)
            alerts.append(alert)

        return alerts


def _meteotogo_alert_urls(root: ElementTree.Element, *, base_url: str) -> list[str]:
    """Return candidate CAP URLs from a Togo RSS feed.

    Parameters
    ----------
    root : ElementTree.Element
        Root XML element of the Togo RSS feed.
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


def _meteotogo_info_texts(xml_payload: str | bytes) -> tuple[list[str], list[str], list[str], list[str]]:
    """Extract Togo area and surrounding provider text from CAP.

    Parameters
    ----------
    xml_payload : str | bytes
        CAP XML document to inspect.

    Returns
    -------
    tuple[list[str], list[str], list[str], list[str]]
        Raw ``areaDesc`` texts, headlines, descriptions, and audiences from
        the document.

    """
    try:
        root = ElementTree.fromstring(xml_payload)
    except ElementTree.ParseError:
        return [], [], [], []

    area_descs: list[str] = []
    headlines: list[str] = []
    descriptions: list[str] = []
    audiences: list[str] = []
    for info in root.iter():
        if local_name(info.tag) != 'info':
            continue
        headline = child_text(info, 'headline')
        description = child_text(info, 'description')
        audience = child_text(info, 'audience')
        if headline:
            headlines.append(headline)
        if description:
            descriptions.append(description)
        if audience:
            audiences.append(audience)
        for area in info:
            if local_name(area.tag) != 'area':
                continue
            area_desc = child_text(area, 'areaDesc')
            if area_desc:
                area_descs.append(area_desc)
    return area_descs, headlines, descriptions, audiences


def _expand_meteotogo_area_names(
    area_descs: list[str],
    headlines: list[str],
    descriptions: list[str],
    audiences: list[str],
) -> list[str]:
    """Expand Togo provider wording into clean region names.

    Parameters
    ----------
    area_descs : list[str]
        Raw ``areaDesc`` texts extracted from CAP.
    headlines : list[str]
        CAP headlines from the same alert.
    descriptions : list[str]
        CAP descriptions from the same alert.
    audiences : list[str]
        CAP audience texts from the same alert.

    Returns
    -------
    list[str]
        Region names found in the provider wording.

    """
    expanded: list[str] = []
    for text in [*area_descs, *headlines, *descriptions, *audiences]:
        normalized = re.sub(r'\s+', ' ', text).strip()
        if not normalized:
            continue
        for name, pattern in TOGO_REGION_PATTERNS:
            if pattern.search(normalized) and name not in expanded:
                expanded.append(name)
    return expanded
