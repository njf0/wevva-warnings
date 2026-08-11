"""Provider backend for JMA operational tropical-cyclone XML products."""

from __future__ import annotations

import re
from datetime import datetime
from xml.etree import ElementTree

from ..models import Alert, TropicalSystem
from ..sources import WarningSource
from ._cap_feed import absolute_url, fetch_feed_root, local_name
from .base import BackendError, WarningBackend, fetch_text

_PRODUCT_CODE_RE = re.compile(r'_(VPT[IW](?:5[0-2]|6[0-5]))_', re.IGNORECASE)
_CENTER_COORDINATE_RE = re.compile(r'([+-]\d+(?:\.\d+)?)([+-]\d+(?:\.\d+)?)\s*/?')


class JMATropicalBackend(WarningBackend):
    """Fetch canonical current tropical systems from JMA's XML update feed."""

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
        """Fetch current tropical systems from JMA's public XML update feed."""
        del lat, lon, lang
        root = fetch_feed_root(source, debug=debug)
        if root is None or not source.url:
            return []

        systems: dict[str, TropicalSystem] = {}
        for document_url, product_code in _jma_tropical_documents(root, base_url=source.url):
            try:
                payload = fetch_text(document_url, headers={'Accept': 'application/xml, text/xml'}, debug=debug)
            except BackendError:
                continue
            system = _parse_jma_tropical_report(
                payload,
                source=source.id,
                url=document_url,
                product_code=product_code,
            )
            if system is None:
                continue
            previous = systems.get(system.id)
            if previous is None or _prefer_system(system, previous):
                systems[system.id] = system

        return sorted(systems.values(), key=lambda system: (system.name.casefold(), system.id))


def _jma_tropical_documents(
    root: ElementTree.Element,
    *,
    base_url: str,
) -> list[tuple[str, str]]:
    """Return the newest update for each dedicated JMA tropical product."""
    newest_by_product: dict[str, tuple[datetime | None, str]] = {}
    for entry in root.iter():
        if local_name(entry.tag) != 'entry':
            continue

        url = _entry_xml_url(entry, base_url=base_url)
        if url is None:
            continue
        product_match = _PRODUCT_CODE_RE.search(url)
        if product_match is None:
            continue
        product_code = product_match.group(1).upper()
        updated = WarningBackend.parse_datetime(_entry_text(entry, 'updated'))

        previous = newest_by_product.get(product_code)
        if previous is None or _is_newer_update(updated, url, previous):
            newest_by_product[product_code] = (updated, url)

    return [
        (url, product_code)
        for product_code, (_, url) in sorted(newest_by_product.items())
    ]


def _entry_xml_url(entry: ElementTree.Element, *, base_url: str) -> str | None:
    for child in entry:
        if local_name(child.tag) != 'link':
            continue
        href = absolute_url(base_url, child.attrib.get('href'))
        if href and (child.attrib.get('type') or '').lower() == 'application/xml':
            return href
    return None


def _is_newer_update(
    updated: datetime | None,
    url: str,
    previous: tuple[datetime | None, str],
) -> bool:
    previous_updated, previous_url = previous
    if updated is not None and previous_updated is not None:
        return (updated, url) > (previous_updated, previous_url)
    if updated is not None:
        return True
    if previous_updated is not None:
        return False
    return url > previous_url


def _parse_jma_tropical_report(
    xml_payload: str,
    *,
    source: str,
    url: str,
    product_code: str,
) -> TropicalSystem | None:
    try:
        root = ElementTree.fromstring(xml_payload)
    except ElementTree.ParseError:
        return None

    head = _first_descendant(root, 'Head')
    body = _first_descendant(root, 'Body')
    if head is None or body is None:
        return None

    title = _child_text(head, 'Title') or ''
    if not _is_tropical_product(title, body):
        return None

    information = _current_tropical_information(body)
    item = _first_child(information, 'Item') if information is not None else None
    if item is None:
        return None

    name, typhoon_number = _name_and_number(item)
    classification = _classification(item, title)
    event_id = _child_text(head, 'EventID')
    identifier = _canonical_identifier(event_id, typhoon_number, title)
    if identifier is None:
        return None

    center_lat, center_lon = _center(item)
    movement = _movement(item)
    pressure = _metric(item, property_type='中心', value_name='Pressure')
    max_wind = _metric(item, property_type='風', value_name='WindSpeed')
    headline = _headline_text(head) or title

    parameters: dict[str, list[str]] = {'JMA Product Code': [product_code]}
    if event_id:
        parameters['JMA Event ID'] = [event_id]
    information_tag = _headline_conditions(head).get('情報タグ')
    if information_tag:
        parameters['JMA Information Tag'] = [information_tag]
    if typhoon_number:
        parameters['JMA Typhoon Number'] = [typhoon_number]
    serial = _child_text(head, 'Serial')
    if serial:
        parameters['JMA Report Serial'] = [serial]
    information_type = _child_text(head, 'InfoType')
    if information_type:
        parameters['JMA Information Type'] = [information_type]
    analysis_time = _child_text(information, 'DateTime')
    if analysis_time:
        parameters['JMA Analysis Time'] = [analysis_time]
    raw_classification = _raw_classification(item)
    if raw_classification:
        parameters['JMA Raw Classification'] = [raw_classification]

    return TropicalSystem(
        id=identifier,
        source=source,
        classification=classification,
        name=name or typhoon_number or event_id or title,
        headline=headline,
        basin='Northwest Pacific',
        url=url,
        issued_at=WarningBackend.parse_datetime(_child_text(head, 'ReportDateTime')),
        advisory_number=serial,
        center_lat=center_lat,
        center_lon=center_lon,
        movement=movement,
        min_pressure=pressure,
        max_wind=max_wind,
        summary=headline,
        parameters=parameters,
    )


def _is_tropical_product(title: str, body: ElementTree.Element) -> bool:
    if '台風' in title or '熱帯低気圧' in title:
        return True
    for node in body.iter():
        if local_name(node.tag) == 'TyphoonNamePart':
            return True
    return False


def _current_tropical_information(body: ElementTree.Element) -> ElementTree.Element | None:
    """Find the current meteorological information, falling back to the first."""
    fallback: ElementTree.Element | None = None
    for information in body.iter():
        if local_name(information.tag) != 'MeteorologicalInfo':
            continue
        if _first_child(information, 'Item') is None:
            continue
        fallback = fallback or information
        date_time = _child_text(information, 'DateTime') or ''
        if '実況' in date_time or _child_attribute(information, 'DateTime', 'type') == '実況':
            return information
    return fallback


def _name_and_number(item: ElementTree.Element) -> tuple[str | None, str | None]:
    for property_node in _properties(item):
        if _child_text(property_node, 'Type') != '呼称':
            continue
        name_part = _first_descendant(property_node, 'TyphoonNamePart')
        if name_part is None:
            continue
        return _child_text(name_part, 'Name'), _child_text(name_part, 'Number')
    return None, None


def _classification(item: ElementTree.Element, title: str) -> str:
    values = [title]
    for property_node in _properties(item):
        if _child_text(property_node, 'Type') == '階級':
            values.append(_descendant_text(property_node, 'TyphoonClass') or '')
    text = ' '.join(values)
    if '元台風' in text or '温帯低気圧' in text:
        return 'Ex-Typhoon'
    if '発達する熱帯低気圧' in text or '熱帯低気圧' in text:
        return 'Developing Tropical Depression'
    if '台風' in text:
        return 'Typhoon'
    return 'Tropical System'


def _raw_classification(item: ElementTree.Element) -> str | None:
    """Return JMA's more specific untransliterated class when it is present."""
    values = [
        value
        for property_node in _properties(item)
        if _child_text(property_node, 'Type') == '階級'
        if (value := _descendant_text(property_node, 'TyphoonClass'))
    ]
    return ', '.join(values) or None


def _canonical_identifier(
    event_id: str | None,
    typhoon_number: str | None,
    title: str,
) -> str | None:
    if event_id:
        return event_id
    if typhoon_number:
        value = typhoon_number.strip().upper()
        if re.fullmatch(r'\d{4}', value):
            return f'TC{value}'
        return value
    return title or None


def _center(item: ElementTree.Element) -> tuple[float | None, float | None]:
    for property_node in _properties(item):
        if _child_text(property_node, 'Type') != '中心':
            continue
        coordinate = _descendant_text(property_node, 'Coordinate')
        if coordinate:
            match = _CENTER_COORDINATE_RE.search(coordinate)
            if match:
                return float(match.group(1)), float(match.group(2))
    return None, None


def _movement(item: ElementTree.Element) -> str | None:
    for property_node in _properties(item):
        if _child_text(property_node, 'Type') != '中心':
            continue
        direction = _descendant_text(property_node, 'Direction')
        speed = _descendant_text(property_node, 'Speed')
        if not direction and not speed:
            continue
        speed_node = _first_descendant(property_node, 'Speed')
        unit = speed_node.attrib.get('unit') if speed_node is not None else None
        if direction and speed:
            return f'{direction} at {speed}{f" {unit}" if unit else ""}'
        return direction or (f'{speed}{f" {unit}" if unit else ""}')
    return None


def _metric(item: ElementTree.Element, *, property_type: str, value_name: str) -> str | None:
    for property_node in _properties(item):
        if _child_text(property_node, 'Type') != property_type:
            continue
        value = _descendant_text(property_node, value_name)
        value_node = _first_descendant(property_node, value_name)
        if value and value_node is not None:
            unit = value_node.attrib.get('unit')
            return f'{value}{f" {unit}" if unit else ""}'
    return None


def _prefer_system(candidate: TropicalSystem, previous: TropicalSystem) -> bool:
    candidate_time = candidate.issued_at
    previous_time = previous.issued_at
    if candidate_time is not None and previous_time is not None and candidate_time != previous_time:
        return candidate_time > previous_time
    if candidate_time is not None and previous_time is None:
        return True
    if candidate_time is None and previous_time is not None:
        return False
    return _product_priority(candidate) > _product_priority(previous)


def _product_priority(system: TropicalSystem) -> int:
    product_code = (system.parameters.get('JMA Product Code') or [''])[0]
    return 2 if product_code.startswith('VPTW') else 1


def _entry_text(entry: ElementTree.Element, name: str) -> str | None:
    return _child_text(entry, name)


def _first_descendant(root: ElementTree.Element, name: str) -> ElementTree.Element | None:
    for node in root.iter():
        if isinstance(node.tag, str) and local_name(node.tag) == name:
            return node
    return None


def _first_child(element: ElementTree.Element, name: str) -> ElementTree.Element | None:
    for child in element:
        if local_name(child.tag) == name:
            return child
    return None


def _child_text(element: ElementTree.Element | None, name: str) -> str | None:
    child = _first_child(element, name) if element is not None else None
    if child is None:
        return None
    text = ''.join(child.itertext()).strip()
    return text or None


def _child_attribute(element: ElementTree.Element, name: str, attribute: str) -> str | None:
    child = _first_child(element, name)
    return child.attrib.get(attribute) if child is not None else None


def _descendant_text(element: ElementTree.Element, name: str) -> str | None:
    node = _first_descendant(element, name)
    if node is None:
        return None
    text = ''.join(node.itertext()).strip()
    return text or None


def _properties(item: ElementTree.Element) -> list[ElementTree.Element]:
    return [node for node in item.iter() if local_name(node.tag) == 'Property']


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


def _headline_text(head: ElementTree.Element) -> str:
    headline = _first_descendant(head, 'Headline')
    return _descendant_text(headline, 'Text') if headline is not None else ''
