"""Provider backend for Japan Meteorological Agency warning XML feeds."""

from __future__ import annotations

import re
from xml.etree import ElementTree

from ..models import Alert
from ..sources import WarningSource
from ._cap_feed import child_text, fetch_feed_root, local_name
from .base import BackendError, WarningBackend, fetch_text

_JMA_WARNING_PRODUCT = re.compile(r'_VPWW(53|5[5-9]|6[01])_')


class JMABackend(WarningBackend):
    """Fetch alerts from JMA's public Atom XML feeds."""

    backend_id = 'jma'

    def fetch_alerts(
        self,
        source: WarningSource,
        *,
        lat: float | None = None,
        lon: float | None = None,
        lang: str | None = None,
        debug: bool = False,
    ) -> list[Alert]:
        """Fetch alerts for a JMA source."""
        del lat, lon, lang
        root = fetch_feed_root(
            source,
            debug=debug,
            headers={'Accept': 'application/atom+xml, application/xml, text/xml'},
        )
        if root is None:
            return []

        alerts: list[Alert] = []
        seen: set[tuple[str, str]] = set()
        for url in _jma_alert_urls(root):
            try:
                payload = fetch_text(url, headers={'Accept': 'application/xml, text/xml'}, debug=debug)
            except BackendError:
                continue
            alert = _parse_jma_warning(payload, source=source, url=url)
            if alert is None:
                continue
            key = (alert.source, alert.id)
            if key in seen:
                continue
            seen.add(key)
            alerts.append(alert)
        return alerts


def _jma_alert_urls(root: ElementTree.Element) -> list[str]:
    """Return JMA warning XML URLs from an Atom feed."""
    urls: list[str] = []
    for entry in root.iter():
        if local_name(entry.tag) != 'entry':
            continue
        href = None
        for child in entry:
            if local_name(child.tag) != 'link':
                continue
            candidate = (child.attrib.get('href') or '').strip()
            if candidate:
                href = candidate
                break
        if href and href.lower().endswith('.xml') and _JMA_WARNING_PRODUCT.search(href):
            urls.append(href)
    return list(dict.fromkeys(urls))


def _parse_jma_warning(payload: str, *, source: WarningSource, url: str) -> Alert | None:
    """Convert one JMA warning bulletin into a normalized alert."""
    try:
        root = ElementTree.fromstring(payload)
    except ElementTree.ParseError:
        return None

    head = _first_child(root, 'Head')
    if head is None:
        return None

    title = child_text(head, 'Title')
    if not title or '気象' not in title or '警報' not in title:
        return None

    bulletin_id = _jma_bulletin_id(url)
    bulletin_headline = _headline_text(head) or title
    onset = WarningBackend.parse_datetime(child_text(head, 'ReportDateTime') or child_text(head, 'TargetDateTime'))

    area_names: list[str] = []
    area_codes: list[str] = []
    active_kind_names: list[str] = []

    for section in root.iter():
        section_name = local_name(section.tag)
        if section_name not in {'Warning', 'Information'}:
            continue
        section_type = (section.attrib.get('type') or '').strip()
        if '市町村等' not in section_type:
            continue
        for item in section:
            if local_name(item.tag) != 'Item':
                continue
            active_names = _active_kind_names(item)
            if not active_names:
                continue
            for area_name, area_code in _item_areas(item):
                if area_name and area_name not in area_names:
                    area_names.append(area_name)
                if area_code and area_code not in area_codes:
                    area_codes.append(area_code)
            for kind_name in active_names:
                if kind_name not in active_kind_names:
                    active_kind_names.append(kind_name)

    if not area_names:
        return None

    event = active_kind_names[0] if len(set(active_kind_names)) == 1 else 'Weather Warnings'
    severity = _severity_from_kind_names(active_kind_names)

    return Alert(
        id=bulletin_id,
        source=source.id,
        event=event,
        headline=title,
        url=url,
        severity=severity,
        urgency='Unknown',
        certainty='Unknown',
        description=bulletin_headline,
        onset=onset,
        area_names=area_names,
        geocodes={'JMA Area Code': area_codes} if area_codes else {},
        parameters={'JMA Warning Kind': active_kind_names} if active_kind_names else {},
    )


def _first_child(element: ElementTree.Element, name: str) -> ElementTree.Element | None:
    """Return the first direct child with the given local name."""
    for child in element:
        if local_name(child.tag) == name:
            return child
    return None


def _headline_text(head: ElementTree.Element) -> str | None:
    """Return the plain-text bulletin headline from a JMA Head element."""
    headline = _first_child(head, 'Headline')
    if headline is None:
        return None
    return child_text(headline, 'Text')


def _active_kind_names(item: ElementTree.Element) -> list[str]:
    """Return active warning/advisory kind names from one JMA item."""
    names: list[str] = []
    for child in item:
        if local_name(child.tag) != 'Kind':
            continue
        status = child_text(child, 'Status')
        name = child_text(child, 'Name')
        if not name or status == '解除':
            continue
        names.append(name)
    return names


def _item_areas(item: ElementTree.Element) -> list[tuple[str | None, str | None]]:
    """Return all areas attached to one JMA warning item."""
    areas: list[tuple[str | None, str | None]] = []

    for child in item:
        child_name = local_name(child.tag)
        if child_name == 'Area':
            areas.append((child_text(child, 'Name'), child_text(child, 'Code')))
            continue
        if child_name != 'Areas':
            continue
        for area in child:
            if local_name(area.tag) != 'Area':
                continue
            areas.append((child_text(area, 'Name'), child_text(area, 'Code')))

    return areas


def _severity_from_kind_names(kind_names: list[str]) -> str:
    """Return a coarse normalized severity from JMA warning kind names."""
    if any('特別警報' in name for name in kind_names):
        return 'Severe'
    if any('警報' in name for name in kind_names):
        return 'Moderate'
    if any('注意報' in name for name in kind_names):
        return 'Minor'
    return 'Unknown'


def _jma_bulletin_id(url: str) -> str:
    """Return a stable alert identifier derived from a JMA XML URL."""
    filename = url.rsplit('/', 1)[-1]
    return filename[:-4] if filename.lower().endswith('.xml') else filename
