"""Provider backend for Malawi Department of Climate Change CAP feeds."""

from __future__ import annotations

import re
from xml.etree import ElementTree

from ..cap import parse_cap_alert
from ..models import Alert
from ..sources import WarningSource
from ._cap_feed import absolute_url, child_text, fetch_feed_root, local_name
from .base import BackendError, WarningBackend, fetch_text


class MetMalawiBackend(WarningBackend):
    """Fetch alerts from Malawi CAP feeds."""

    backend_id = 'metmalawi'

    def fetch_alerts(
        self,
        source: WarningSource,
        *,
        lat: float | None = None,
        lon: float | None = None,
        lang: str | None = None,
        debug: bool = False,
    ) -> list[Alert]:
        """Fetch alerts for a Malawi CAP source.

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
            Alerts parsed from linked Malawi CAP documents.

        """
        del lat, lon
        root = fetch_feed_root(source, debug=debug)
        if root is None or not source.url:
            return []

        urls = _metmalawi_alert_urls(root, base_url=source.url)
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

            area_descs, descriptions, audiences = _metmalawi_info_texts(alert_payload)
            expanded_area_names = _expand_metmalawi_area_names(area_descs, descriptions, audiences)
            if expanded_area_names:
                alert.area_names = expanded_area_names

            key = (alert.source, alert.id)
            if key in seen:
                continue
            seen.add(key)
            alerts.append(alert)

        return alerts


def _metmalawi_alert_urls(root: ElementTree.Element, *, base_url: str) -> list[str]:
    """Return candidate CAP URLs from a Malawi RSS feed.

    Parameters
    ----------
    root : ElementTree.Element
        Root XML element of the Malawi RSS feed.
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


def _metmalawi_info_texts(xml_payload: str | bytes) -> tuple[list[str], list[str], list[str]]:
    """Extract Malawi area, description, and audience text from CAP.

    Parameters
    ----------
    xml_payload : str | bytes
        CAP XML document to inspect.

    Returns
    -------
    tuple[list[str], list[str], list[str]]
        Raw ``areaDesc`` texts, descriptions, and audiences from the document.

    """
    try:
        root = ElementTree.fromstring(xml_payload)
    except ElementTree.ParseError:
        return [], [], []

    area_descs: list[str] = []
    descriptions: list[str] = []
    audiences: list[str] = []
    for info in root.iter():
        if local_name(info.tag) != 'info':
            continue
        description = child_text(info, 'description')
        audience = child_text(info, 'audience')
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
    return area_descs, descriptions, audiences


def _expand_metmalawi_area_names(
    area_descs: list[str],
    descriptions: list[str],
    audiences: list[str],
) -> list[str]:
    """Expand Malawi provider wording into more useful area names.

    Parameters
    ----------
    area_descs : list[str]
        Raw ``areaDesc`` texts extracted from CAP.
    descriptions : list[str]
        CAP descriptions for the same alert.
    audiences : list[str]
        CAP audience texts for the same alert.

    Returns
    -------
    list[str]
        Region and district names derived from Malawi provider wording.

    """
    expanded: list[str] = []

    for text in [*area_descs, *descriptions]:
        normalized = ' '.join(text.split()).strip(' .')
        if not normalized:
            continue

        for name in _metmalawi_region_names(normalized):
            if name not in expanded:
                expanded.append(name)

        for name in _metmalawi_district_names(normalized):
            if name not in expanded:
                expanded.append(name)

    for text in audiences:
        normalized = ' '.join(text.split()).strip()
        if not normalized:
            continue
        for match in re.finditer(r'Category\s+\d+\s*:\s*([^•]+)', normalized, flags=re.IGNORECASE):
            for name in _split_metmalawi_names(match.group(1)):
                if name not in expanded:
                    expanded.append(name)

    return expanded


def _metmalawi_region_names(text: str) -> list[str]:
    """Return region-style names implied by Malawi provider text.

    Parameters
    ----------
    text : str
        One Malawi provider text string.

    Returns
    -------
    list[str]
        Region-style area names inferred from the text.

    """
    lower = text.lower()
    names: list[str] = []

    if 'southern malawi' in lower:
        names.append('Southern Malawi')

    if 'southern' in lower and 'central' in lower and 'lakes' in lower:
        names.extend(['Southern Region', 'Central Region', 'Lakeshore Areas'])
        return names

    if 'southern region' in lower:
        names.append('Southern Region')
    if 'central region' in lower:
        names.append('Central Region')
    if 'lakeshore' in lower:
        names.append('Lakeshore Areas')

    return names


def _metmalawi_district_names(text: str) -> list[str]:
    """Extract district names from Malawi description wording.

    Parameters
    ----------
    text : str
        One Malawi provider text string.

    Returns
    -------
    list[str]
        District names found in the text.

    """
    names: list[str] = []

    include_match = re.search(
        r'Districts?[^.]*?\binclude\s+([^.]+)',
        text,
        flags=re.IGNORECASE,
    )
    if include_match:
        names.extend(_split_metmalawi_names(include_match.group(1)))

    valley_match = re.search(
        r'districts? of\s+([^.]+)',
        text,
        flags=re.IGNORECASE,
    )
    if valley_match:
        names.extend(_split_metmalawi_names(valley_match.group(1)))

    return list(dict.fromkeys(names))


def _split_metmalawi_names(text: str) -> list[str]:
    """Split Malawi district or region lists into individual names.

    Parameters
    ----------
    text : str
        Delimited list text from Malawi provider wording.

    Returns
    -------
    list[str]
        Individual place names extracted from the text.

    """
    normalized = re.sub(r'\bparts of\b', '', text, flags=re.IGNORECASE)
    normalized = normalized.replace(' ndi ', ' and ')
    normalized = re.sub(r'\s+', ' ', normalized).strip(' .,:;')
    parts = re.split(r',|\band\b', normalized, flags=re.IGNORECASE)
    cleaned: list[str] = []
    for part in parts:
        name = part.strip(' .,:;')
        if name:
            cleaned.append(name)
    return cleaned
