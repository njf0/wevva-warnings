"""Provider backend for Tanzania Meteorological Authority CAP feeds."""

from __future__ import annotations

import re
from xml.etree import ElementTree

from ..cap import parse_cap_alert
from ..models import Alert
from ..sources import WarningSource
from ._cap_feed import absolute_url, child_text, fetch_feed_root, local_name
from .base import BackendError, WarningBackend, fetch_text


class TMABackend(WarningBackend):
    """Fetch alerts from Tanzania Meteorological Authority CAP feeds."""

    backend_id = 'tma'

    def fetch_alerts(
        self,
        source: WarningSource,
        *,
        lat: float | None = None,
        lon: float | None = None,
        lang: str | None = None,
        debug: bool = False,
    ) -> list[Alert]:
        """Fetch alerts for a TMA CAP source.

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
            Alerts parsed from linked TMA CAP documents.

        """
        del lat, lon
        root = fetch_feed_root(source, debug=debug)
        if root is None or not source.url:
            return []

        urls = _tma_alert_urls(root, base_url=source.url)
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

            expanded_area_names = _expand_tma_area_names(_tma_area_descs(alert_payload))
            if expanded_area_names:
                alert.area_names = expanded_area_names

            key = (alert.source, alert.id)
            if key in seen:
                continue
            seen.add(key)
            alerts.append(alert)

        return alerts


def _tma_alert_urls(root: ElementTree.Element, *, base_url: str) -> list[str]:
    """Return candidate CAP URLs from a TMA RSS feed.

    Parameters
    ----------
    root : ElementTree.Element
        Root XML element of the TMA RSS feed.
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
        if url and '/tz-tma-' in url.lower() and url.lower().endswith('.xml'):
            urls.append(url)
    return list(dict.fromkeys(urls))


def _tma_area_descs(xml_payload: str | bytes) -> list[str]:
    """Extract raw TMA ``areaDesc`` texts from one CAP document.

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


def _expand_tma_area_names(descriptions: list[str]) -> list[str]:
    """Expand TMA area text into flat region and island names.

    Parameters
    ----------
    descriptions : list[str]
        Raw ``areaDesc`` texts extracted from CAP.

    Returns
    -------
    list[str]
        Flattened region and island names derived from the TMA phrasing.

    """
    expanded: list[str] = []
    for description in descriptions:
        text = ' '.join(description.split()).strip(' .')
        if not text:
            continue

        normalized = _normalize_tma_area_text(text)
        if not normalized:
            continue

        for part in _split_tma_area_parts(normalized):
            if part not in expanded:
                expanded.append(part)

    return expanded


def _normalize_tma_area_text(text: str) -> str:
    """Remove TMA boilerplate from an ``areaDesc`` string.

    Parameters
    ----------
    text : str
        Raw TMA ``areaDesc`` text.

    Returns
    -------
    str
        Simplified text containing the meaningful area names.

    """
    normalized = text
    normalized = re.sub(r'^\s*Areas of\s+', '', normalized, flags=re.IGNORECASE)
    normalized = re.sub(r'^\s*areas of\s+', '', normalized, flags=re.IGNORECASE)
    normalized = re.sub(r'^\s*(?:the )?southern part of\s+', 'southern part of ', normalized, flags=re.IGNORECASE)
    normalized = re.sub(r'^\s*mikoa ya\s+', '', normalized, flags=re.IGNORECASE)
    normalized = re.sub(r'^\s*maeneo machache ya mikoa(?: ya)?\s+', '', normalized, flags=re.IGNORECASE)
    normalized = re.sub(r'\s+regions?\b', '', normalized, flags=re.IGNORECASE)
    normalized = re.sub(r'\s+region\b', '', normalized, flags=re.IGNORECASE)
    normalized = re.sub(r'\s+', ' ', normalized)
    return normalized.strip(' .')


def _split_tma_area_parts(text: str) -> list[str]:
    """Split normalized TMA area text into individual names.

    Parameters
    ----------
    text : str
        Normalized TMA area text.

    Returns
    -------
    list[str]
        Individual region and island names.

    """
    items: list[str] = []
    text = text.replace(' together with ', ', ')
    text = text.replace(' pamoja na ', ', ')

    for parenthetical in re.findall(r'\(([^)]*)\)', text):
        cleaned = parenthetical
        cleaned = re.sub(r'^\s*including\s+', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'^\s*ikijumuisha\s+', '', cleaned, flags=re.IGNORECASE)
        for part in _split_tma_connectors(cleaned):
            if part not in items:
                items.append(part)

    without_parentheses = re.sub(r'\([^)]*\)', '', text)
    for part in _split_tma_connectors(without_parentheses):
        if part not in items:
            items.append(part)

    return items


def _split_tma_connectors(text: str) -> list[str]:
    """Split TMA area text on commas and language-specific connectors.

    Parameters
    ----------
    text : str
        Area text to split.

    Returns
    -------
    list[str]
        Trimmed area name parts.

    """
    normalized = re.sub(r'\s+', ' ', text).strip(' .')
    if not normalized:
        return []

    parts = [normalized]
    for separator in (',', ' and ', ' na '):
        next_parts: list[str] = []
        for part in parts:
            next_parts.extend(segment for segment in part.split(separator))
        parts = next_parts

    cleaned_parts: list[str] = []
    for part in parts:
        cleaned = part.strip(' .')
        if not cleaned:
            continue
        cleaned = re.sub(r'^(?:ya|of)\s+', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'^\s*visiwa?\b vya\s+', '', cleaned, flags=re.IGNORECASE)
        if not re.search(r'\bmafia isles?\b', cleaned, flags=re.IGNORECASE):
            cleaned = re.sub(r'\s+isles?\b', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s+', ' ', cleaned)
        if cleaned:
            cleaned_parts.append(cleaned)
    return cleaned_parts
