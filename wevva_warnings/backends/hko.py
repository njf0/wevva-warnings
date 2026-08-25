"""Provider backend for Hong Kong Observatory alert and tropical-track feeds."""

from __future__ import annotations

import re
from urllib.parse import urljoin
from xml.etree import ElementTree

from ..models import Alert, Geometry, TropicalProduct, TropicalSystem
from ..sources import WarningSource
from ._cap_feed import child_text, fetch_cap_documents, fetch_feed_root, local_name
from .base import BackendError, WarningBackend, fetch_text

_HKO_WIND_RE = re.compile(r'(-?\d+(?:\.\d+)?)')


class HKOBackend(WarningBackend):
    """Fetch Hong Kong Observatory CAP alerts and tropical-track products."""

    backend_id = 'hko'

    def fetch_alerts(
        self,
        source: WarningSource,
        *,
        lat: float | None = None,
        lon: float | None = None,
        lang: str | None = None,
        debug: bool = False,
    ) -> list[Alert]:
        """Fetch alerts for a Hong Kong CAP source."""
        del lat, lon
        root = fetch_feed_root(source, debug=debug)
        if root is None or not source.url:
            return []
        return fetch_cap_documents(
            source,
            _hko_alert_urls(root, base_url=source.url),
            preferred_lang=lang or source.lang,
            debug=debug,
        )

    def fetch_tropical_systems(
        self,
        source: WarningSource,
        *,
        lat: float | None = None,
        lon: float | None = None,
        lang: str | None = None,
        debug: bool = False,
    ) -> list[TropicalSystem]:
        """Fetch current systems from HKO's documented tropical-track XML."""
        del lat, lon, lang
        root = fetch_feed_root(source, debug=debug)
        if root is None or not source.url:
            return []

        systems: list[TropicalSystem] = []
        for cyclone in root.iter():
            if local_name(cyclone.tag) != 'TropicalCyclone':
                continue
            system_id = child_text(cyclone, 'TropicalCycloneID')
            english_name = child_text(cyclone, 'TropicalCycloneEnglishName')
            chinese_name = child_text(cyclone, 'TropicalCycloneChineseName')
            track_url = _hko_track_url(child_text(cyclone, 'TropicalCycloneURL'), base_url=source.url)
            if not system_id or not track_url:
                continue
            try:
                payload = fetch_text(track_url, headers={'Accept': 'application/xml, text/xml'}, debug=debug)
            except BackendError:
                continue
            system = _parse_hko_tropical_track(
                payload,
                source=source.id,
                system_id=system_id,
                english_name=english_name,
                chinese_name=chinese_name,
                url=track_url,
            )
            if system is not None:
                systems.append(system)

        return sorted(systems, key=lambda system: (system.name.casefold(), system.id))

    def fetch_tropical_products(
        self,
        source: WarningSource,
        system: TropicalSystem,
        *,
        debug: bool = False,
    ) -> list[TropicalProduct]:
        """Fetch HKO's structured forecast positions for one system."""
        del source
        track_url = system.data_urls.get('tropical_cyclone_track')
        if not track_url:
            return []
        try:
            payload = fetch_text(
                track_url,
                headers={'Accept': 'application/xml, text/xml'},
                debug=debug,
            )
        except BackendError:
            return []
        forecast = _hko_forecast_product_data(payload, system=system)
        if forecast is None:
            return []
        return [
            TropicalProduct(
                kind='forecast',
                label='Forecast',
                title=f'{system.name} Forecast',
                issued_at=system.issued_at,
                url=track_url,
                data=forecast,
            )
        ]


def _hko_alert_urls(root: ElementTree.Element, *, base_url: str) -> list[str]:
    """Return candidate CAP URLs from a Hong Kong Atom feed."""
    urls: list[str] = []
    for entry in root.iter():
        if local_name(entry.tag) != 'entry':
            continue
        for child in entry:
            if local_name(child.tag) != 'link':
                continue
            href = (child.get('href') or '').strip()
            rel = (child.get('rel') or '').lower()
            if not href or rel != 'alternate' or not href.lower().endswith('.xml'):
                continue
            urls.append(urljoin(base_url, href))
    return list(dict.fromkeys(urls))


def _hko_track_url(value: str | None, *, base_url: str) -> str | None:
    """Return an HTTPS HKO tropical-track URL from one list entry."""
    if not value:
        return None
    url = urljoin(base_url, value.strip())
    if url.startswith('http://www.weather.gov.hk/'):
        return f'https://{url.removeprefix("http://")}'
    return url


def _parse_hko_tropical_track(
    xml_payload: str,
    *,
    source: str,
    system_id: str,
    english_name: str | None,
    chinese_name: str | None,
    url: str,
) -> TropicalSystem | None:
    """Normalize one HKO tropical cyclone track document."""
    try:
        root = ElementTree.fromstring(xml_payload)
    except ElementTree.ParseError:
        return None

    report = _first_descendant(root, 'WeatherReport')
    if report is None:
        return None

    analysis = _first_descendant(report, 'AnalysisInformation')
    past = [node for node in report.iter() if local_name(node.tag) == 'PastInformation']
    forecast = [node for node in report.iter() if local_name(node.tag) == 'ForecastInformation']
    forecast_fixes = _hko_timed_forecast_fixes(forecast)
    current = analysis if analysis is not None else _latest_information(past)
    if current is None:
        return None

    center_lat, center_lon = _hko_coordinates(current)
    name = english_name or _descendant_text(report, 'TropicalCycloneName') or chinese_name or system_id
    classification = _descendant_text(current, 'Intensity') or 'Tropical Cyclone'
    max_wind = _descendant_text(current, 'MaximumWind')
    parameters: dict[str, list[str]] = {'HKO Tropical Cyclone ID': [system_id]}
    if english_name:
        parameters['HKO English Name'] = [english_name]
    if chinese_name:
        parameters['HKO Chinese Name'] = [chinese_name]
    bulletin_type = _descendant_text(_first_descendant(root, 'BulletinHeader'), 'BulletinType')
    if bulletin_type:
        parameters['HKO Bulletin Type'] = [bulletin_type]
    analysis_time = _descendant_text(current, 'Time')
    if analysis_time:
        parameters['HKO Analysis Time'] = [analysis_time]
    peak = _hko_peak_information([*past, *([analysis] if analysis is not None else [])])
    if peak is not None:
        peak_intensity, peak_wind, peak_time = peak
        if peak_intensity:
            parameters['HKO Peak Intensity'] = [peak_intensity]
        if peak_wind:
            parameters['HKO Peak Maximum Wind'] = [peak_wind]
        if peak_time:
            parameters['HKO Peak Time'] = [peak_time]

    geometries: dict[str, Geometry] = {}
    observed_track = _hko_track_geometry([*past, *([analysis] if analysis is not None else [])])
    if observed_track is not None:
        geometries['observed_track'] = observed_track
    forecast_track = _hko_track_geometry(forecast_fixes)
    if forecast_track is not None:
        geometries['forecast_track'] = forecast_track

    return TropicalSystem(
        id=system_id,
        source=source,
        classification=classification,
        name=name,
        headline=f'{classification}: {name}',
        basin='Northwest Pacific / South China Sea',
        url=url,
        issued_at=WarningBackend.parse_datetime(
            _descendant_text(_first_descendant(root, 'BulletinHeader'), 'BulletinTime')
        ),
        center_lat=center_lat,
        center_lon=center_lon,
        max_wind=max_wind,
        summary=f'Hong Kong Observatory tropical cyclone track product for {name}.',
        data_urls={'tropical_cyclone_track': url},
        geometries=geometries,
        parameters=parameters,
    )


def _first_descendant(element: ElementTree.Element, name: str) -> ElementTree.Element | None:
    for node in element.iter():
        if local_name(node.tag) == name:
            return node
    return None


def _descendant_text(element: ElementTree.Element | None, name: str) -> str | None:
    if element is None:
        return None
    node = _first_descendant(element, name)
    if node is None:
        return None
    text = ''.join(node.itertext()).strip()
    return text or None


def _latest_information(nodes: list[ElementTree.Element]) -> ElementTree.Element | None:
    """Return the latest dated HKO information block, retaining source order on ties."""
    latest: ElementTree.Element | None = None
    latest_time = None
    for node in nodes:
        node_time = WarningBackend.parse_datetime(_descendant_text(node, 'Time'))
        if latest is None or (node_time is not None and (latest_time is None or node_time > latest_time)):
            latest = node
            latest_time = node_time
    return latest


def _hko_coordinates(element: ElementTree.Element) -> tuple[float | None, float | None]:
    return _hko_coordinate(_descendant_text(element, 'Latitude'), latitude=True), _hko_coordinate(
        _descendant_text(element, 'Longitude'), latitude=False
    )


def _hko_coordinate(value: str | None, *, latitude: bool) -> float | None:
    if not value:
        return None
    text = value.strip().upper()
    hemisphere = text[-1:]
    try:
        coordinate = float(text[:-1] if hemisphere in {'N', 'S', 'E', 'W'} else text)
    except ValueError:
        return None
    if (latitude and hemisphere == 'S') or (not latitude and hemisphere == 'W'):
        return -coordinate
    return coordinate


def _hko_track_geometry(nodes: list[ElementTree.Element]) -> Geometry | None:
    points: list[list[float]] = []
    for node in nodes:
        lat, lon = _hko_coordinates(node)
        if lat is not None and lon is not None:
            points.append([lon, lat])
    if len(points) < 2:
        return None
    return {'type': 'LineString', 'coordinates': points}


def _hko_timed_forecast_fixes(
    nodes: list[ElementTree.Element],
) -> list[ElementTree.Element]:
    """Return genuine HKO forecast fixes ordered by their numeric hour index.

    HKO also publishes untimed ``ForecastInformation`` vertices for drawing a
    smooth curve. Those vertices are presentation geometry, not forecast fixes,
    and must not become marker positions in the normalized forecast track.
    """
    fixes: list[tuple[int, int, ElementTree.Element]] = []
    for source_order, node in enumerate(nodes):
        valid_at = _descendant_text(node, 'Time')
        index = _descendant_text(node, 'Index')
        if not valid_at or not index:
            continue
        try:
            lead_hours = int(index)
        except ValueError:
            continue
        if lead_hours < 0:
            continue
        fixes.append((lead_hours, source_order, node))
    return [node for _, _, node in sorted(fixes)]


def _hko_forecast_product_data(
    payload: str,
    *,
    system: TropicalSystem,
) -> dict[str, object] | None:
    """Return HKO forecast blocks while preserving HKO-specific quantities."""
    try:
        root = ElementTree.fromstring(payload)
    except ElementTree.ParseError:
        return None
    document_id = (root.attrib.get('tcid') or '').strip()
    document_name = _descendant_text(root, 'TropicalCycloneName')
    if document_id:
        if document_id != system.id:
            return None
    elif not document_name or document_name.strip().casefold() != system.name.strip().casefold():
        return None

    forecast_nodes = [node for node in root.iter() if local_name(node.tag) == 'ForecastInformation']
    points: list[dict[str, object]] = []
    for node in _hko_timed_forecast_fixes(forecast_nodes):
        latitude, longitude = _hko_coordinates(node)
        if latitude is None or longitude is None:
            continue
        point: dict[str, object] = {
            'latitude': latitude,
            'longitude': longitude,
        }
        valid_at = _descendant_text(node, 'Time')
        intensity = _descendant_text(node, 'Intensity')
        wind = _descendant_text(node, 'MaximumWind')
        if valid_at:
            point['valid_at'] = valid_at
        if intensity:
            point['intensity'] = intensity
        if wind:
            point['maximum_wind'] = wind
        points.append(point)
    if not points:
        return None
    return {'points': points}


def _hko_peak_information(
    nodes: list[ElementTree.Element],
) -> tuple[str | None, str | None, str | None] | None:
    """Return HKO's highest reported wind and its matching intensity and time."""
    peak: tuple[float, str | None, str | None, str | None] | None = None
    for node in nodes:
        wind = _descendant_text(node, 'MaximumWind')
        match = _HKO_WIND_RE.search(wind or '')
        if match is None:
            continue
        try:
            speed = float(match.group(1))
        except ValueError:
            continue
        candidate = (
            speed,
            _descendant_text(node, 'Intensity'),
            wind,
            _descendant_text(node, 'Time'),
        )
        if peak is None or candidate[0] > peak[0]:
            peak = candidate
    if peak is None:
        return None
    _, intensity, wind, time = peak
    return intensity, wind, time
