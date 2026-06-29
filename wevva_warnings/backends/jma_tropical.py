"""Provider backend for JMA tropical-system discussion XML."""

from __future__ import annotations

import re
from xml.etree import ElementTree

from ..models import Alert, TropicalSystem
from ..sources import WarningSource
from ._cap_feed import absolute_url, fetch_feed_root, local_name
from .base import BackendError, WarningBackend, fetch_text

_TROPICAL_MARKERS = ('熱帯低気圧', '台風', '元台風')
_FULLWIDTH_DIGIT_MAP = str.maketrans('０１２３４５６７８９', '0123456789')
_COORDINATE_RE = re.compile(
    r'([北南])緯\s*([0-9０-９]+)度([0-9０-９]+)分、\s*([東西])経\s*([0-9０-９]+)度([0-9０-９]+)分'
)
_PRESSURE_RE = re.compile(r'中心の気圧は([0-9０-９]+)ヘクトパスカル')
_MAX_WIND_RE = re.compile(r'最大風速は([0-9０-９]+)メートル')
_MOVEMENT_RE = re.compile(r'１時間に(?:およそ)?([0-9０-９]+)キロの速さで(.+?)へ進んでいます')


class JMATropicalBackend(WarningBackend):
    """Fetch tropical-system style products from JMA's XML pull feed."""

    backend_id = 'jma_tropical'

    def fetch_alerts(
        self,
        source: WarningSource,
        *,
        lat: float | None = None,
        lon: float | None = None,
        lang: str | None = None,
        debug: bool = False,
    ) -> list[Alert]:
        """Return no ordinary alerts for JMA tropical-system feeds."""
        del source, lat, lon, lang, debug
        return []

    def fetch_tropical_systems(
        self,
        source: WarningSource,
        *,
        lat: float | None = None,
        lon: float | None = None,
        lang: str | None = None,
        debug: bool = False,
    ) -> list[TropicalSystem]:
        """Fetch tropical systems from JMA's public XML update feed."""
        del lat, lon, lang
        root = fetch_feed_root(source, debug=debug)
        if root is None or not source.url:
            return []

        systems: list[TropicalSystem] = []
        for document_url in _jma_tropical_document_urls(root, base_url=source.url):
            try:
                payload = fetch_text(document_url, headers={'Accept': 'application/xml, text/xml'}, debug=debug)
            except BackendError:
                continue
            system = _parse_jma_tropical_report(payload, source=source.id, url=document_url)
            if system is not None:
                systems.append(system)
        return systems


def _jma_tropical_document_urls(root: ElementTree.Element, *, base_url: str) -> list[str]:
    urls: list[str] = []
    for entry in root.iter():
        if local_name(entry.tag) != 'entry':
            continue
        title = _entry_text(entry, 'title')
        content = _entry_text(entry, 'content')
        haystack = f'{title}\n{content}'
        if not any(marker in haystack for marker in _TROPICAL_MARKERS):
            continue
        for child in entry:
            if local_name(child.tag) != 'link':
                continue
            href = absolute_url(base_url, child.attrib.get('href'))
            if href and (child.attrib.get('type') or '').lower() == 'application/xml':
                urls.append(href)
                break
    return list(dict.fromkeys(urls))


def _parse_jma_tropical_report(
    xml_payload: str,
    *,
    source: str,
    url: str,
) -> TropicalSystem | None:
    try:
        root = ElementTree.fromstring(xml_payload)
    except ElementTree.ParseError:
        return None

    head = _first_descendant(root, 'Head')
    body = _first_descendant(root, 'Body')
    if head is None:
        return None

    title = _child_text(head, 'Title') or ''
    if not any(marker in title for marker in _TROPICAL_MARKERS):
        headline_text = _headline_text(head)
        if not any(marker in headline_text for marker in _TROPICAL_MARKERS):
            return None
    else:
        headline_text = _headline_text(head)

    conditions = _headline_conditions(head)
    tc_number = conditions.get('台風番号') or conditions.get('TC番号')
    info_tag = conditions.get('情報タグ')
    summary = _summary_text(body)

    center_lat, center_lon = _parse_coordinates(summary)
    movement = _parse_movement(summary)
    pressure = _parse_metric(summary, _PRESSURE_RE, suffix=' hPa')
    max_wind = _parse_metric(summary, _MAX_WIND_RE, suffix=' m/s')

    identifier = tc_number or _child_text(head, 'EventID') or title
    classification = _classification_for_title(title, info_tag)
    name = tc_number or _child_text(head, 'EventID') or title

    parameters: dict[str, list[str]] = {}
    event_id = _child_text(head, 'EventID')
    if event_id:
        parameters['JMA Event ID'] = [event_id]
    if info_tag:
        parameters['JMA Information Tag'] = [info_tag]
    if tc_number:
        parameters['JMA Tropical Number'] = [tc_number]

    return TropicalSystem(
        id=identifier,
        source=source,
        classification=classification,
        name=name,
        headline=headline_text or title,
        basin='Northwest Pacific',
        url=url,
        issued_at=WarningBackend.parse_datetime(_child_text(head, 'ReportDateTime')),
        center_lat=center_lat,
        center_lon=center_lon,
        movement=movement,
        min_pressure=pressure,
        max_wind=max_wind,
        summary=summary or headline_text or title,
        parameters=parameters,
    )


def _entry_text(entry: ElementTree.Element, name: str) -> str:
    for child in entry:
        if local_name(child.tag) != name:
            continue
        return ''.join(child.itertext()).strip()
    return ''


def _first_descendant(root: ElementTree.Element, name: str) -> ElementTree.Element | None:
    for node in root.iter():
        if isinstance(node.tag, str) and local_name(node.tag) == name:
            return node
    return None


def _child_text(element: ElementTree.Element | None, name: str) -> str | None:
    if element is None:
        return None
    for child in element:
        if local_name(child.tag) != name:
            continue
        text = ''.join(child.itertext()).strip()
        return text or None
    return None


def _headline_text(head: ElementTree.Element) -> str:
    headline = _first_descendant(head, 'Headline')
    if headline is None:
        return ''
    for child in headline:
        if local_name(child.tag) == 'Text':
            return ''.join(child.itertext()).strip()
    return ''


def _headline_conditions(head: ElementTree.Element) -> dict[str, str]:
    conditions: dict[str, str] = {}
    headline = _first_descendant(head, 'Headline')
    if headline is None:
        return conditions

    for node in headline.iter():
        if local_name(node.tag) != 'Kind':
            continue
        name = _child_text(node, 'Name')
        condition = _child_text(node, 'Condition')
        if name and condition:
            conditions[name] = condition
    return conditions


def _summary_text(body: ElementTree.Element | None) -> str:
    if body is None:
        return ''
    for node in body.iter():
        if local_name(node.tag) != 'Text':
            continue
        if node.attrib.get('type') != '本文':
            continue
        text = ''.join(node.itertext()).strip()
        if text:
            return text
    return ''


def _normalize_digits(text: str) -> str:
    return text.translate(_FULLWIDTH_DIGIT_MAP)


def _parse_coordinates(text: str) -> tuple[float | None, float | None]:
    match = _COORDINATE_RE.search(text)
    if not match:
        return None, None
    lat_sign = 1.0 if match.group(1) == '北' else -1.0
    lon_sign = 1.0 if match.group(4) == '東' else -1.0
    lat_deg = float(_normalize_digits(match.group(2)))
    lat_min = float(_normalize_digits(match.group(3)))
    lon_deg = float(_normalize_digits(match.group(5)))
    lon_min = float(_normalize_digits(match.group(6)))
    lat = lat_sign * (lat_deg + lat_min / 60.0)
    lon = lon_sign * (lon_deg + lon_min / 60.0)
    return round(lat, 3), round(lon, 3)


def _parse_metric(text: str, pattern: re.Pattern[str], *, suffix: str) -> str | None:
    match = pattern.search(text)
    if not match:
        return None
    return f'{_normalize_digits(match.group(1))}{suffix}'


def _parse_movement(text: str) -> str | None:
    match = _MOVEMENT_RE.search(text)
    if not match:
        return None
    speed = _normalize_digits(match.group(1))
    direction = match.group(2).strip()
    return f'{direction} at {speed} km/h'


def _classification_for_title(title: str, info_tag: str | None) -> str:
    text = f'{title} {info_tag or ""}'
    if '元台風' in text:
        return 'Ex-Typhoon'
    if '発達する熱帯低気圧' in text or '熱帯低気圧' in text:
        return 'Developing Tropical Depression'
    if '台風' in text:
        return 'Typhoon'
    return 'Tropical System'
