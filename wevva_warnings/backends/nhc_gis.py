"""Provider backend for NHC/CPHC GIS RSS tropical cyclone feeds."""

from __future__ import annotations

import io
from datetime import datetime
from email.utils import parsedate_to_datetime
from html import unescape
import re
import zipfile
from typing import Any
from xml.etree import ElementTree

from ..models import Alert, Geometry, TropicalProduct, TropicalSystem
from ..sources import WarningSource
from ._cap_feed import absolute_url, child_text, fetch_feed_root, local_name
from ._tropical_text import plain_text_to_markdown
from .base import BackendError, WarningBackend, fetch_bytes, fetch_text

_ATCF_FROM_GUID_RE = re.compile(r'(?:summary|atcf|gis-[a-z0-9-]+)-([a-z]{2}\d{6})-', re.IGNORECASE)
_ATCF_FROM_TITLE_RE = re.compile(r'\(([A-Z0-9]+)/(?:([a-z]{2}\d{6}))\)', re.IGNORECASE)
_ADVISORY_NUMBER_RE = re.compile(r'Advisory\s+#([0-9A-Z]+)', re.IGNORECASE)
_GEOMETRY_ASSET_KEYS = ('forecast_track', 'cone', 'watch_warning')
_WALLET_RE = re.compile(r'^(?:AT|EP|CP)[1-5]$', re.IGNORECASE)
_BR_RE = re.compile(r'<br\s*/?>', re.IGNORECASE)
_PRE_TAG_RE = re.compile(r'</?pre(?:\s[^>]*)?>', re.IGNORECASE)
_WMO_HEADER_RE = re.compile(r'^[A-Z]{4}\d{2}\s+[A-Z]{4}\s+\d{6}(?:\s+[A-Z]{3})?$')
_MARKDOWN_ESCAPE_RE = re.compile(r'([\\`*_{}\[\]<>])')
_NHC_PRODUCT_SPECS = (
    ('TCP', 'advisory', 'Public Advisory'),
    ('TCD', 'analysis', 'Forecast Discussion'),
    ('PWS', 'probabilities', 'Wind Probabilities'),
    ('TCV', 'warnings', 'Warnings'),
    ('TCU', 'update', 'Update'),
)


class NHCGISBackend(WarningBackend):
    """Fetch tropical systems from NHC and CPHC GIS RSS feeds."""

    backend_id = 'nhc_gis'

    def fetch_alerts(
        self,
        source: WarningSource,
        *,
        lat: float | None = None,
        lon: float | None = None,
        lang: str | None = None,
        debug: bool = False,
    ) -> list[Alert]:
        """Return no ordinary alerts for NHC GIS tropical-system feeds."""
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
        """Fetch tropical systems for an NHC/CPHC GIS source."""
        del lat, lon, lang
        root = fetch_feed_root(source, debug=debug)
        if root is None or not source.url:
            return []

        grouped: dict[str, dict[str, Any]] = {}
        for item in root.iter():
            if local_name(item.tag) != 'item':
                continue

            title = child_text(item, 'title') or ''
            guid = child_text(item, 'guid') or ''
            link = absolute_url(source.url, child_text(item, 'link'))
            atcf = _extract_atcf_id(title, guid)
            if not atcf:
                continue

            bucket = grouped.setdefault(atcf, {'data_urls': {}})

            summary = _summary_node(item)
            if summary is not None:
                bucket.update(_summary_fields(summary))
                bucket['url'] = link or bucket.get('url')
                item_description = child_text(item, 'description')
                if item_description:
                    bucket['summary'] = item_description

            asset_key = _asset_key(title)
            if asset_key and link:
                bucket['data_urls'][asset_key] = link

            advisory_number = _extract_advisory_number(title)
            if advisory_number and not bucket.get('advisory_number'):
                bucket['advisory_number'] = advisory_number

        _populate_geometry_assets(grouped, debug=debug)
        _populate_advisory_information(grouped, debug=debug)

        systems: list[TropicalSystem] = []
        for atcf, data in grouped.items():
            classification = self.text_or_none(data.get('classification'))
            name = self.text_or_none(data.get('name'))
            headline = self.text_or_none(data.get('headline'))
            if not classification or not name or not headline:
                continue

            systems.append(
                TropicalSystem(
                    id=atcf,
                    source=source.id,
                    classification=classification,
                    name=name,
                    headline=headline,
                    basin=_basin_for_source(source.id),
                    url=self.text_or_none(data.get('url')),
                    issued_at=self.parse_datetime(data.get('issued_at')),
                    advisory_number=self.text_or_none(data.get('advisory_number')),
                    center_lat=_maybe_float(data.get('center_lat')),
                    center_lon=_maybe_float(data.get('center_lon')),
                    movement=self.text_or_none(data.get('movement')),
                    min_pressure=self.text_or_none(data.get('min_pressure')),
                    max_wind=self.text_or_none(data.get('max_wind')),
                    summary=self.text_or_none(data.get('summary')) or self.text_or_none(data.get('headline')),
                    data_urls=dict(data.get('data_urls') or {}),
                    geometries=dict(data.get('geometries') or {}),
                    parameters=_parameters_from_bucket(data),
                )
            )

        return systems

    def fetch_tropical_products(
        self,
        source: WarningSource,
        system: TropicalSystem,
        *,
        debug: bool = False,
    ) -> list[TropicalProduct]:
        """Fetch current NHC/CPHC wallet text products for one observation."""
        del source
        wallet = _wallet_for_system(system)
        if wallet is None:
            return []

        products: list[TropicalProduct] = []
        for product_code, kind, label in _NHC_PRODUCT_SPECS:
            feed_url = f'https://www.nhc.noaa.gov/xml/{product_code}{wallet}.xml'
            try:
                payload = fetch_text(
                    feed_url,
                    headers={'Accept': 'application/rss+xml, application/xml, text/xml'},
                    debug=debug,
                )
            except BackendError:
                continue
            product = _parse_nhc_product_feed(
                payload,
                system=system,
                product_code=product_code,
                kind=kind,
                label=label,
            )
            if product is not None:
                products.append(product)
        return products


def _summary_node(item: ElementTree.Element) -> ElementTree.Element | None:
    for node in item.iter():
        if local_name(node.tag) == 'Cyclone':
            return node
    return None


def _summary_fields(summary: ElementTree.Element) -> dict[str, Any]:
    center_lat, center_lon = _parse_center(child_text(summary, 'center'))
    return {
        'classification': child_text(summary, 'type'),
        'name': child_text(summary, 'name'),
        'wallet': child_text(summary, 'wallet'),
        'atcf': child_text(summary, 'atcf'),
        'issued_at': child_text(summary, 'datetime'),
        'movement': child_text(summary, 'movement'),
        'min_pressure': child_text(summary, 'pressure'),
        'headline': child_text(summary, 'headline'),
        'center_lat': center_lat,
        'center_lon': center_lon,
    }


def _parse_center(value: str | None) -> tuple[float | None, float | None]:
    if not value:
        return None, None
    parts = [part.strip() for part in value.split(',', 1)]
    if len(parts) != 2:
        return None, None
    return _maybe_float(parts[0]), _maybe_float(parts[1])


def _maybe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).strip())
    except ValueError:
        return None


def _extract_atcf_id(title: str, guid: str) -> str | None:
    match = _ATCF_FROM_GUID_RE.search(guid)
    if match:
        return match.group(1).lower()

    match = _ATCF_FROM_TITLE_RE.search(title)
    if match:
        atcf = match.group(2)
        if atcf:
            return atcf.lower()
    return None


def _extract_advisory_number(title: str) -> str | None:
    match = _ADVISORY_NUMBER_RE.search(title)
    if match:
        return match.group(1)
    return None


def _asset_key(title: str) -> str | None:
    lowered = title.lower()
    if lowered.startswith('atcf xml prototype'):
        return 'atcf_xml'
    if 'forecast track [kmz]' in lowered:
        return 'forecast_track'
    if 'cone of uncertainty [kmz]' in lowered:
        return 'cone'
    if 'watches/warnings [kmz]' in lowered:
        return 'watch_warning'
    if 'wind field [shp]' in lowered:
        return 'wind_field'
    if lowered.startswith('advisory #') and 'forecast [shp]' in lowered:
        return 'forecast_area'
    if lowered.startswith('preliminary best track [shp]'):
        return 'best_track'
    return None


def _basin_for_source(source_id: str) -> str | None:
    lowered = source_id.lower()
    if 'atlantic' in lowered:
        return 'Atlantic'
    if 'eastern_pacific' in lowered:
        return 'Eastern Pacific'
    if 'central_pacific' in lowered:
        return 'Central Pacific'
    return None


def _parameters_from_bucket(bucket: dict[str, Any]) -> dict[str, list[str]]:
    parameters: dict[str, list[str]] = {}
    for key, label in [
        ('wallet', 'NHC Wallet'),
        ('atcf', 'ATCF ID'),
        ('saffir_simpson_category', 'NHC Saffir-Simpson Category'),
        ('watches_warnings', 'NHC Watches and Warnings'),
    ]:
        value = bucket.get(key)
        if value:
            parameters[label] = [str(value)]
    location_references = bucket.get('location_references')
    if isinstance(location_references, list) and location_references:
        parameters['NHC Location References'] = [str(reference) for reference in location_references]
    return parameters


def _wallet_for_system(system: TropicalSystem) -> str | None:
    """Return a valid temporary NHC wallet locator from observation metadata."""
    values = system.parameters.get('NHC Wallet') or []
    for value in values:
        wallet = value.strip().upper()
        if _WALLET_RE.fullmatch(wallet):
            return wallet
    return None


def _parse_nhc_product_feed(
    payload: str,
    *,
    system: TropicalSystem,
    product_code: str,
    kind: str,
    label: str,
) -> TropicalProduct | None:
    """Parse one current wallet feed and reject stale wallet contents."""
    try:
        root = ElementTree.fromstring(payload)
    except ElementTree.ParseError:
        return None

    item = next((node for node in root.iter() if local_name(node.tag) == 'item'), None)
    if item is None:
        return None
    raw_content = child_text(item, 'description')
    if not raw_content or system.id.upper() not in unescape(raw_content).upper():
        return None

    content = _normalize_nhc_product_content(raw_content, product_code=product_code, system=system)
    if not content:
        return None
    if product_code in {'PWS', 'TCU'}:
        return TropicalProduct(
            kind=kind,
            label=label,
            title=child_text(item, 'title'),
            issued_at=_parse_rfc2822_datetime(child_text(item, 'pubDate')),
            content=content,
            content_format='plain',
            url=child_text(item, 'link'),
            data={'product_code': product_code},
        )
    markdown = None
    if product_code in {'TCP', 'TCD'}:
        markdown = _nhc_product_markdown(content, product_code=product_code)
    content = markdown or plain_text_to_markdown(
        content,
        fixed_width=product_code not in {'TCP', 'TCD'},
    )
    return TropicalProduct(
        kind=kind,
        label=label,
        title=child_text(item, 'title'),
        issued_at=_parse_rfc2822_datetime(child_text(item, 'pubDate')),
        content=content,
        url=child_text(item, 'link'),
        data={'product_code': product_code},
    )


def _normalize_nhc_product_content(
    value: str,
    *,
    product_code: str,
    system: TropicalSystem,
) -> str:
    """Decode known NHC RSS layout without rewriting meteorological prose."""
    text = unescape(value).replace('\r\n', '\n').replace('\r', '\n')
    text = _BR_RE.sub('\n', text)
    text = _PRE_TAG_RE.sub('', text)
    lines = [line.rstrip() for line in text.splitlines()]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()

    wallet = _wallet_for_system(system)
    expected_awips = f'{product_code}{wallet}' if wallet else None
    if (
        len(lines) >= 3
        and re.fullmatch(r'\d{3,4}', lines[0].strip())
        and _WMO_HEADER_RE.fullmatch(lines[1].strip())
        and expected_awips is not None
        and lines[2].strip().upper() == expected_awips
    ):
        lines = lines[3:]
        while lines and not lines[0].strip():
            lines.pop(0)

    return '\n'.join(lines).strip()


def _nhc_product_markdown(content: str, *, product_code: str) -> str | None:
    """Format recognized NHC advisory/discussion layout as faithful Markdown."""
    lines = content.splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)

    if product_code == 'TCP':
        if not lines or lines[0].strip().upper() != 'BULLETIN':
            return None
        lines.pop(0)
        while lines and not lines[0].strip():
            lines.pop(0)
        if not lines or 'advisory' not in lines[0].casefold():
            return None
    elif product_code == 'TCD':
        if not lines or 'discussion' not in lines[0].casefold():
            return None
    else:
        return None

    output = [f'# {_escape_markdown_line(lines[0].strip())}']
    index = 1
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if index + 1 < len(lines) and stripped and _is_nhc_heading_ruler(lines[index + 1]):
            _append_markdown_blank(output)
            output.append(f'## {_escape_markdown_line(stripped)}')
            index += 2
            if stripped.startswith('SUMMARY OF ') and stripped.endswith('INFORMATION'):
                index = _append_indented_product_block(output, lines, index)
            continue

        if stripped == 'FORECAST POSITIONS AND MAX WINDS':
            _append_markdown_blank(output)
            output.append('## FORECAST POSITIONS AND MAX WINDS')
            index = _append_indented_product_block(output, lines, index + 1)
            continue

        if stripped.startswith('...') and stripped.endswith('...'):
            _append_markdown_blank(output)
            output.append(f'> {_escape_markdown_line(stripped)}')
        elif stripped:
            output.append(_escape_markdown_line(line))
        else:
            _append_markdown_blank(output)
        index += 1

    while output and not output[-1]:
        output.pop()
    return '\n'.join(output)


def _append_indented_product_block(
    output: list[str],
    lines: list[str],
    index: int,
) -> int:
    """Append one provider-delimited fixed-width block as Markdown code."""
    while index < len(lines) and not lines[index].strip():
        index += 1
    block_start = index
    while index < len(lines) and lines[index].strip():
        index += 1
    if index > block_start:
        _append_markdown_blank(output)
        output.extend(f'    {line}' for line in lines[block_start:index])
        _append_markdown_blank(output)
    return index


def _append_markdown_blank(output: list[str]) -> None:
    if output and output[-1]:
        output.append('')


def _is_nhc_heading_ruler(value: str) -> bool:
    return re.fullmatch(r'-{3,}', value.strip()) is not None


def _escape_markdown_line(value: str) -> str:
    """Escape inline Markdown punctuation without changing rendered prose."""
    return _MARKDOWN_ESCAPE_RE.sub(r'\\\1', value)


def _parse_rfc2822_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None


def _populate_geometry_assets(grouped: dict[str, dict[str, Any]], *, debug: bool) -> None:
    for bucket in grouped.values():
        geometries: dict[str, Geometry] = {}
        for key in _GEOMETRY_ASSET_KEYS:
            url = (bucket.get('data_urls') or {}).get(key)
            if not isinstance(url, str) or not url:
                continue
            geometry = _fetch_asset_geometry(url, debug=debug)
            if geometry is not None:
                geometries[key] = geometry
        if geometries:
            bucket['geometries'] = geometries


def _populate_advisory_information(grouped: dict[str, dict[str, Any]], *, debug: bool) -> None:
    """Add compact current facts from each linked official ATCF advisory XML."""
    for bucket in grouped.values():
        url = (bucket.get('data_urls') or {}).get('atcf_xml')
        if not isinstance(url, str) or not url:
            continue
        try:
            payload = fetch_text(url, headers={'Accept': 'application/xml, text/xml'}, debug=debug)
        except BackendError:
            continue
        for key, value in _parse_advisory_information(payload).items():
            if value and not bucket.get(key):
                bucket[key] = value


def _parse_advisory_information(payload: str) -> dict[str, Any]:
    """Return at-a-glance facts from NHC's linked ATCF advisory XML."""
    try:
        root = ElementTree.fromstring(payload)
    except ElementTree.ParseError:
        return {}

    values: dict[str, Any] = {}
    advisory_number = _first_text(root, 'advisoryNumber')
    if advisory_number:
        values['advisory_number'] = advisory_number
    max_wind = _advisory_maximum_wind(root)
    if max_wind:
        values['max_wind'] = max_wind
    category = _useful_text(_first_text(root, 'systemSaffirSimpsonCategory'))
    if category:
        values['saffir_simpson_category'] = category
    references = [
        reference
        for tag in ('systemGeoRefPt1', 'systemGeoRefPt2')
        if (reference := _first_text(root, tag))
    ]
    if references:
        values['location_references'] = references
    watches_warnings = _watch_warning_summary(_first_text(root, 'message'))
    if watches_warnings:
        values['watches_warnings'] = watches_warnings
    return values


def _advisory_maximum_wind(root: ElementTree.Element) -> str | None:
    values: list[str] = []
    for tag, unit in (
        ('systemIntensityKts', 'kt'),
        ('systemIntensityMph', 'mph'),
        ('systemIntensityKph', 'km/h'),
    ):
        value = _useful_text(_first_text(root, tag))
        if value:
            values.append(f'{value} {unit}')
    if not values:
        return None
    return f'{values[0]} ({" / ".join(values[1:])})' if len(values) > 1 else values[0]


def _watch_warning_summary(message: str | None) -> str | None:
    """Extract the current watch/warning paragraph from an advisory message."""
    if not message:
        return None
    heading = 'SUMMARY OF WATCHES AND WARNINGS IN EFFECT:'
    _, separator, remainder = message.partition(heading)
    if not separator:
        return None
    paragraph = remainder.strip().split('\n\n', 1)[0]
    summary = ' '.join(line.strip() for line in paragraph.splitlines() if line.strip())
    return _useful_text(summary)


def _useful_text(value: str | None) -> str | None:
    if not value or value.strip().casefold() in {'n/a', 'none.', 'none'}:
        return None
    return value.strip()


def _fetch_asset_geometry(url: str, *, debug: bool) -> Geometry | None:
    try:
        payload = fetch_bytes(url, debug=debug)
    except BackendError:
        return None
    return _parse_kmz_geometry(payload)


def _parse_kmz_geometry(payload: bytes) -> Geometry | None:
    kml_payload = payload
    try:
        if zipfile.is_zipfile(io.BytesIO(payload)):
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                kml_name = next((name for name in archive.namelist() if name.lower().endswith('.kml')), None)
                if not kml_name:
                    return None
                kml_payload = archive.read(kml_name)
    except (OSError, KeyError, zipfile.BadZipFile):
        return None

    try:
        root = ElementTree.fromstring(kml_payload)
    except ElementTree.ParseError:
        return None

    geometries: list[Geometry] = []
    for placemark in root.iter():
        if local_name(placemark.tag) != 'Placemark':
            continue
        geometry = _placemark_geometry(placemark)
        if geometry is not None:
            geometries.append(geometry)

    return _combine_geometries(geometries)


def _placemark_geometry(placemark: ElementTree.Element) -> Geometry | None:
    for child in placemark:
        geometry = _element_geometry(child)
        if geometry is not None:
            return geometry
    return None


def _element_geometry(element: ElementTree.Element) -> Geometry | None:
    tag = local_name(element.tag)
    if tag == 'Point':
        coordinates = _parse_coordinates_text(_first_text(element, 'coordinates'))
        if len(coordinates) == 1:
            return _with_bbox({'type': 'Point', 'coordinates': coordinates[0]})
        return None
    if tag == 'LineString':
        coordinates = _parse_coordinates_text(_first_text(element, 'coordinates'))
        if len(coordinates) >= 2:
            return _with_bbox({'type': 'LineString', 'coordinates': coordinates})
        return None
    if tag == 'Polygon':
        rings: list[list[list[float]]] = []
        outer = _parse_coordinates_text(_boundary_coordinates(element, 'outerBoundaryIs'))
        if len(outer) < 4:
            return None
        rings.append(outer)
        for child in element:
            if local_name(child.tag) != 'innerBoundaryIs':
                continue
            hole = _parse_coordinates_text(_first_text(child, 'coordinates'))
            if len(hole) >= 4:
                rings.append(hole)
        return _with_bbox({'type': 'Polygon', 'coordinates': rings})
    if tag == 'MultiGeometry':
        geometries: list[Geometry] = []
        for child in element:
            geometry = _element_geometry(child)
            if geometry is not None:
                geometries.append(geometry)
        return _combine_geometries(geometries)

    for child in element:
        geometry = _element_geometry(child)
        if geometry is not None:
            return geometry
    return None


def _combine_geometries(geometries: list[Geometry]) -> Geometry | None:
    if not geometries:
        return None
    if len(geometries) == 1:
        return _with_bbox(dict(geometries[0]))

    geometry_types = {str(geometry.get('type') or '') for geometry in geometries}
    if geometry_types == {'Point'}:
        return _with_bbox({'type': 'MultiPoint', 'coordinates': [geometry['coordinates'] for geometry in geometries]})
    if geometry_types == {'LineString'}:
        return _with_bbox(
            {'type': 'MultiLineString', 'coordinates': [geometry['coordinates'] for geometry in geometries]}
        )
    if geometry_types == {'Polygon'}:
        return _with_bbox({'type': 'MultiPolygon', 'coordinates': [geometry['coordinates'] for geometry in geometries]})

    return _with_bbox({'type': 'GeometryCollection', 'geometries': geometries})


def _parse_coordinates_text(value: str | None) -> list[list[float]]:
    if not value:
        return []

    points: list[list[float]] = []
    for token in value.replace('\n', ' ').split():
        parts = [part.strip() for part in token.split(',')]
        if len(parts) < 2:
            continue
        try:
            lon = float(parts[0])
            lat = float(parts[1])
        except ValueError:
            continue
        points.append([lon, lat])
    return points


def _first_text(element: ElementTree.Element, local_tag: str) -> str | None:
    for child in element.iter():
        if local_name(child.tag) == local_tag:
            text = child.text.strip() if child.text else ''
            return text or None
    return None


def _boundary_coordinates(element: ElementTree.Element, boundary_tag: str) -> str | None:
    for child in element:
        if local_name(child.tag) == boundary_tag:
            return _first_text(child, 'coordinates')
    return None


def _with_bbox(geometry: Geometry) -> Geometry:
    positions = _geometry_positions(geometry)
    if not positions:
        return geometry

    longitudes = [position[0] for position in positions]
    latitudes = [position[1] for position in positions]
    enriched = dict(geometry)
    enriched['bbox'] = [
        round(min(longitudes), 3),
        round(min(latitudes), 3),
        round(max(longitudes), 3),
        round(max(latitudes), 3),
    ]
    return enriched


def _geometry_positions(geometry: Geometry) -> list[tuple[float, float]]:
    geometry_type = geometry.get('type')
    coordinates = geometry.get('coordinates') or []

    if geometry_type == 'Point' and isinstance(coordinates, list) and len(coordinates) >= 2:
        lon, lat = coordinates[:2]
        if isinstance(lon, (int, float)) and isinstance(lat, (int, float)):
            return [(float(lon), float(lat))]
        return []

    if geometry_type in {'LineString', 'MultiPoint'}:
        positions: list[tuple[float, float]] = []
        for point in coordinates:
            if (
                isinstance(point, list)
                and len(point) >= 2
                and isinstance(point[0], (int, float))
                and isinstance(point[1], (int, float))
            ):
                positions.append((float(point[0]), float(point[1])))
        return positions

    if geometry_type == 'Polygon':
        positions = []
        for ring in coordinates:
            for point in ring:
                if (
                    isinstance(point, list)
                    and len(point) >= 2
                    and isinstance(point[0], (int, float))
                    and isinstance(point[1], (int, float))
                ):
                    positions.append((float(point[0]), float(point[1])))
        return positions

    if geometry_type == 'MultiLineString':
        positions = []
        for line in coordinates:
            for point in line:
                if (
                    isinstance(point, list)
                    and len(point) >= 2
                    and isinstance(point[0], (int, float))
                    and isinstance(point[1], (int, float))
                ):
                    positions.append((float(point[0]), float(point[1])))
        return positions

    if geometry_type == 'MultiPolygon':
        positions = []
        for polygon in coordinates:
            for ring in polygon:
                for point in ring:
                    if (
                        isinstance(point, list)
                        and len(point) >= 2
                        and isinstance(point[0], (int, float))
                        and isinstance(point[1], (int, float))
                    ):
                        positions.append((float(point[0]), float(point[1])))
        return positions

    if geometry_type == 'GeometryCollection':
        positions = []
        for child in geometry.get('geometries') or []:
            if isinstance(child, dict):
                positions.extend(_geometry_positions(child))
        return positions

    return []
