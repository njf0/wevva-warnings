"""Provider backend for JMA operational tropical-cyclone XML products."""

from __future__ import annotations

import re
from datetime import datetime
from xml.etree import ElementTree

from ..models import Alert, Geometry, TropicalProduct, TropicalSystem
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
        strict: bool = False,
    ) -> list[TropicalSystem]:
        """Fetch current tropical systems from JMA's public XML update feed."""
        del lat, lon, lang
        root = fetch_feed_root(source, debug=debug, **({'strict': True} if strict else {}))
        if root is None or not source.url:
            return []

        systems: dict[str, TropicalSystem] = {}
        for document_url, product_code in _jma_tropical_documents(root, base_url=source.url):
            try:
                payload = fetch_text(document_url, headers={'Accept': 'application/xml, text/xml'}, debug=debug)
            except BackendError:
                if strict:
                    raise
                continue
            if strict:
                try:
                    ElementTree.fromstring(payload)
                except ElementTree.ParseError as error:
                    raise BackendError(f'Invalid JMA tropical XML: {document_url}') from error
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

    def fetch_tropical_products(
        self,
        source: WarningSource,
        system: TropicalSystem,
        *,
        debug: bool = False,
    ) -> list[TropicalProduct]:
        """Fetch structured forecast detail from the selected JMA report."""
        del source
        if not system.url:
            return []
        try:
            payload = fetch_text(
                system.url,
                headers={'Accept': 'application/xml, text/xml'},
                debug=debug,
            )
        except BackendError:
            return []

        product_codes = system.parameters.get('JMA Product Code') or []
        product_code = product_codes[0] if product_codes else ''
        parsed = _parse_jma_tropical_report(
            payload,
            source=system.source,
            url=system.url,
            product_code=product_code,
        )
        if parsed is None or parsed.id != system.id:
            return []
        data = _jma_forecast_product_data(payload)
        if data is None:
            return []
        has_forecast = bool(data.get('points'))
        kind = 'forecast' if has_forecast else 'analysis'
        label = 'Forecast' if has_forecast else 'Analysis'
        return [
            TropicalProduct(
                kind=kind,
                label=label,
                title=f'{system.name} {label}',
                issued_at=parsed.issued_at,
                url=system.url,
                data=data,
            )
        ]


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
    geometries: dict[str, Geometry] = {}
    forecast_track = _forecast_track(
        body,
        current_center=(center_lat, center_lon),
    )
    if forecast_track is not None:
        geometries['forecast_track'] = forecast_track
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
        geometries=geometries,
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
        position = _degree_position(property_node, 'Coordinate')
        if position is not None:
            return position
    return None, None


def _forecast_track(
    body: ElementTree.Element,
    *,
    current_center: tuple[float | None, float | None],
) -> Geometry | None:
    """Return forecast centres from the same current VPTW report."""
    coordinates: list[list[float]] = []
    current_lat, current_lon = current_center
    if current_lat is not None and current_lon is not None:
        coordinates.append([current_lon, current_lat])

    for information in body.iter():
        if local_name(information.tag) != 'MeteorologicalInfo':
            continue
        information_type = _child_attribute(information, 'DateTime', 'type') or ''
        if not information_type.startswith('予報'):
            continue
        item = _first_child(information, 'Item')
        if item is None:
            continue
        point = _forecast_center(item)
        if point is None:
            continue
        lat, lon = point
        coordinate = [lon, lat]
        if not coordinates or coordinate != coordinates[-1]:
            coordinates.append(coordinate)

    if len(coordinates) < 2:
        return None
    return {'type': 'LineString', 'coordinates': coordinates}


def _forecast_center(item: ElementTree.Element) -> tuple[float, float] | None:
    for property_node in _properties(item):
        if _child_text(property_node, 'Type') != '中心':
            continue
        position = _degree_position(property_node, 'BasePoint')
        if position is not None:
            return position
    return None


def _jma_forecast_product_data(payload: str) -> dict[str, object] | None:
    """Return JMA analysis and forecast facts without constructing areas."""
    try:
        root = ElementTree.fromstring(payload)
    except ElementTree.ParseError:
        return None
    body = _first_descendant(root, 'Body')
    if body is None:
        return None

    analysis = _jma_analysis_product_data(body)
    points: list[dict[str, object]] = []
    for information in body.iter():
        if local_name(information.tag) != 'MeteorologicalInfo':
            continue
        forecast_type = _child_attribute(information, 'DateTime', 'type') or ''
        if not forecast_type.startswith('予報'):
            continue
        item = _first_child(information, 'Item')
        point = _forecast_center(item) if item is not None else None
        if item is None or point is None:
            continue
        latitude, longitude = point
        product_point: dict[str, object] = {
            'latitude': latitude,
            'longitude': longitude,
        }
        lead_hours = _jma_forecast_lead_hours(forecast_type)
        valid_at = _child_text(information, 'DateTime')
        if lead_hours is not None:
            product_point['lead_hours'] = lead_hours
        elif forecast_type:
            product_point['forecast_label'] = forecast_type
        if valid_at:
            product_point['valid_at'] = valid_at
        product_point.update(_jma_item_product_data(item))
        points.append(product_point)
    data: dict[str, object] = {}
    if analysis:
        data['analysis'] = analysis
    if points:
        data['points'] = points
    return data or None


def _jma_analysis_product_data(body: ElementTree.Element) -> dict[str, object] | None:
    """Return current facts that add to the ordinary tropical-system fields."""
    information = _current_tropical_information(body)
    item = _first_child(information, 'Item') if information is not None else None
    if item is None:
        return None

    item_data = _jma_item_product_data(item)
    analysis: dict[str, object] = {}
    valid_at = _child_text(information, 'DateTime')
    if valid_at:
        analysis['valid_at'] = valid_at
    classification_details = item_data.get('classification_details')
    if (
        isinstance(classification_details, dict)
        and any(key in classification_details for key in ('area_class', 'intensity_class'))
    ):
        analysis['classification'] = item_data['classification']
        analysis['classification_details'] = classification_details
    for key in (
        'location',
        'maximum_gust',
        'source_values',
        'probability_circle',
        'wind_areas',
    ):
        if key in item_data:
            analysis[key] = item_data[key]

    # A validity time alone, or the raw cyclone class already represented by
    # TropicalSystem, does not justify a separate current-only product.
    return analysis if any(key != 'valid_at' for key in analysis) else None


def _jma_item_product_data(item: ElementTree.Element) -> dict[str, object]:
    """Return restrained provider-specific facts from one JMA item."""
    data: dict[str, object] = {}
    classification_details = _jma_classification_data(item)
    classification = _jma_classification(classification_details)
    if classification:
        data['classification'] = classification
        data['classification_details'] = classification_details

    center_property = _property(item, '中心')
    if center_property is not None:
        location = _descendant_text(center_property, 'Location')
        if location:
            data['location'] = location
        movement, movement_values = _jma_movement_data(center_property)
        if movement:
            data['movement'] = movement

    pressure = _metric(item, property_type='中心', value_name='Pressure')
    wind = _metric(
        item,
        property_type='風',
        value_name='WindSpeed',
        value_type='最大風速',
    )
    gust = _metric(
        item,
        property_type='風',
        value_name='WindSpeed',
        value_type='最大瞬間風速',
    )
    if pressure:
        data['minimum_pressure'] = pressure
    if wind:
        data['maximum_wind'] = wind
    if gust:
        data['maximum_gust'] = gust

    source_values: dict[str, object] = {}
    if _jma_source_values_are_useful(movement_values):
        source_values['movement_speed'] = _jma_value_collection(movement_values)
    maximum_wind_values = _jma_wind_values(item, value_type='最大風速')
    maximum_gust_values = _jma_wind_values(item, value_type='最大瞬間風速')
    if _jma_source_values_are_useful(maximum_wind_values):
        source_values['maximum_wind'] = _jma_value_collection(maximum_wind_values)
    if _jma_source_values_are_useful(maximum_gust_values):
        source_values['maximum_gust'] = _jma_value_collection(maximum_gust_values)
    if source_values:
        data['source_values'] = source_values

    probability_circle = _jma_probability_circle_data(item)
    if probability_circle:
        data['probability_circle'] = probability_circle
    wind_areas = _jma_wind_area_data(item)
    if wind_areas:
        data['wind_areas'] = wind_areas
    return data


def _jma_classification_data(item: ElementTree.Element) -> dict[str, str]:
    property_node = _property(item, '階級')
    if property_node is None:
        return {}
    fields = (
        ('typhoon_class', 'TyphoonClass'),
        ('area_class', 'AreaClass'),
        ('intensity_class', 'IntensityClass'),
    )
    return {
        key: value
        for key, element_name in fields
        if (value := _descendant_text(property_node, element_name))
    }


def _jma_classification(details: dict[str, str]) -> str | None:
    """Return a stable display value without losing distinct source parts."""
    components: list[str] = []
    cyclone_class = details.get('typhoon_class')
    intensity_class = details.get('intensity_class')
    if cyclone_class:
        components.append(cyclone_class)
    if intensity_class and intensity_class not in components:
        components.append(intensity_class)
    if not components and (area_class := details.get('area_class')):
        components.append(area_class)
    return ' / '.join(components) or None


def _jma_movement_data(
    center_property: ElementTree.Element,
) -> tuple[str | None, list[dict[str, str]]]:
    center_part = _first_descendant(center_property, 'CenterPart')
    movement_parent = center_part if center_part is not None else center_property
    direction_node = _first_child(movement_parent, 'Direction')
    direction = _jma_node_text(direction_node)
    speeds = [
        value
        for child in movement_parent
        if local_name(child.tag) == 'Speed'
        if (value := _jma_measurement_data(child))
    ]
    speed = _jma_display_measurement(speeds[0]) if speeds else None
    if direction and speed:
        return f'{direction} at {speed}', speeds
    return direction or speed, speeds


def _jma_wind_values(item: ElementTree.Element, *, value_type: str) -> list[dict[str, str]]:
    property_node = _property(item, '風')
    if property_node is None:
        return []
    wind_part = _first_descendant(property_node, 'WindPart')
    return (
        _jma_measurements(wind_part, 'WindSpeed', value_type=value_type)
        if wind_part is not None
        else []
    )


def _jma_probability_circle_data(item: ElementTree.Element) -> dict[str, object]:
    center_property = _property(item, '中心')
    circle = _first_descendant(center_property, 'ProbabilityCircle') if center_property is not None else None
    if circle is None:
        return {}
    data: dict[str, object] = {}
    circle_type = circle.attrib.get('type')
    if circle_type:
        data['type'] = circle_type
    axes = _jma_axes_data(circle)
    if axes:
        data['axes'] = axes
    return data


def _jma_wind_area_data(item: ElementTree.Element) -> list[dict[str, object]]:
    wind_property = _property(item, '風')
    if wind_property is None:
        return []

    areas: list[dict[str, object]] = []
    for part in wind_property.iter():
        if local_name(part.tag) != 'WarningAreaPart':
            continue
        area: dict[str, object] = {}
        area_type = part.attrib.get('type')
        if area_type:
            area['type'] = area_type
        thresholds = _jma_measurements(part, 'WindSpeed')
        if thresholds:
            area['threshold'] = _jma_value_collection(thresholds)
        axes = _jma_axes_data(part)
        if axes:
            area['axes'] = axes
        if area:
            areas.append(area)
    return areas


def _jma_axes_data(element: ElementTree.Element) -> list[dict[str, object]]:
    axes: list[dict[str, object]] = []
    for axis_node in element.iter():
        if local_name(axis_node.tag) != 'Axis':
            continue
        axis: dict[str, object] = {}
        direction = _jma_node_text(_first_descendant(axis_node, 'Direction'))
        if direction:
            axis['direction'] = direction
        radius_pairs = [
            (node, value)
            for node in axis_node.iter()
            if local_name(node.tag) == 'Radius'
            if (value := _jma_measurement_data(node))
        ]
        radii = [value for _node, value in radius_pairs]
        radius_types = list(
            dict.fromkeys(
                node.attrib['type']
                for node, _value in radius_pairs
                if node.attrib.get('type')
            )
        )
        if len(radius_types) == 1:
            axis['radius_type'] = radius_types[0]
        elif radius_types:
            for node, radius in radius_pairs:
                if radius_type := node.attrib.get('type'):
                    radius['type'] = radius_type
        if radii:
            axis['radii'] = radii
        if radii:
            axes.append(axis)
    return axes


def _jma_measurements(
    element: ElementTree.Element | None,
    element_name: str,
    *,
    value_type: str | None = None,
) -> list[dict[str, str]]:
    if element is None:
        return []
    values: list[dict[str, str]] = []
    for node in element.iter():
        if local_name(node.tag) != element_name:
            continue
        if value_type is not None and node.attrib.get('type') != value_type:
            continue
        value = _jma_measurement_data(node)
        if value:
            values.append(value)
    return values


def _jma_measurement_data(node: ElementTree.Element | None) -> dict[str, str]:
    """Return only value attributes that carry meteorological meaning."""
    if node is None:
        return {}
    text = ''.join(node.itertext()).strip()
    condition = node.attrib.get('condition')
    if not text and not condition:
        return {}
    data: dict[str, str] = {}
    if text:
        data['value'] = text
        if unit := node.attrib.get('unit'):
            data['unit'] = unit
    if condition:
        data['condition'] = condition
    return data


def _jma_node_text(node: ElementTree.Element | None) -> str | None:
    if node is None:
        return None
    return (
        ''.join(node.itertext()).strip()
        or node.attrib.get('description')
        or node.attrib.get('condition')
    )


def _jma_display_measurement(value: dict[str, str]) -> str | None:
    text = value.get('value')
    if text:
        unit = value.get('unit')
        numeric = text.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
        if unit and re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)', numeric):
            return f'{text} {unit}'
        return text
    return value.get('condition')


def _jma_source_values_are_useful(values: list[dict[str, str]]) -> bool:
    """Return whether values add units, conditions, or distinct source facts."""
    if not values:
        return False
    if any(value.get('condition') for value in values):
        return True
    units = {value.get('unit') for value in values if value.get('unit')}
    facts = {(value.get('value'), value.get('unit')) for value in values}
    return len(units) > 1 or len(facts) > 1


def _jma_value_collection(values: list[dict[str, str]]) -> dict[str, object]:
    """Lift a shared condition while retaining provider-published units."""
    conditions = {value.get('condition') for value in values}
    condition = next(iter(conditions)) if len(conditions) == 1 else None
    compact_values: list[dict[str, str]] = []
    for value in values:
        compact = dict(value)
        if condition:
            compact.pop('condition', None)
        if compact:
            compact_values.append(compact)
    collection: dict[str, object] = {}
    if compact_values:
        collection['values'] = compact_values
    if condition:
        collection['condition'] = condition
    return collection


def _jma_forecast_lead_hours(forecast_type: str) -> int | None:
    """Return the explicit hour horizon from a JMA forecast-type label."""
    normalized = forecast_type.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
    match = re.fullmatch(r'予報\s*(\d+)\s*時間後', normalized)
    if match is None:
        return None
    lead_hours = int(match.group(1))
    return lead_hours if lead_hours > 0 else None


def _degree_position(
    element: ElementTree.Element,
    element_name: str,
) -> tuple[float, float] | None:
    for node in element.iter():
        if local_name(node.tag) != element_name:
            continue
        if node.attrib.get('type') != '中心位置（度）':
            continue
        text = ''.join(node.itertext()).strip()
        match = _CENTER_COORDINATE_RE.search(text)
        if match is None:
            continue
        lat = float(match.group(1))
        lon = float(match.group(2))
        if -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0:
            return lat, lon
    return None


def _movement(item: ElementTree.Element) -> str | None:
    for property_node in _properties(item):
        if _child_text(property_node, 'Type') != '中心':
            continue
        movement, _source_values = _jma_movement_data(property_node)
        if movement:
            return movement
    return None


def _metric(
    item: ElementTree.Element,
    *,
    property_type: str,
    value_name: str,
    value_type: str | None = None,
) -> str | None:
    for property_node in _properties(item):
        if _child_text(property_node, 'Type') != property_type:
            continue
        for value_node in property_node.iter():
            if local_name(value_node.tag) != value_name:
                continue
            if value_type is not None and value_node.attrib.get('type') != value_type:
                continue
            value = ''.join(value_node.itertext()).strip()
            if value:
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


def _property(item: ElementTree.Element, property_type: str) -> ElementTree.Element | None:
    for property_node in _properties(item):
        if _child_text(property_node, 'Type') == property_type:
            return property_node
    return None


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
