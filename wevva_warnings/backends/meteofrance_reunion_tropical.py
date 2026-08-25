"""Provider backend for Météo-France La Réunion RSMC cyclone data."""

from __future__ import annotations

import codecs
import json
import logging
from datetime import UTC, datetime
from http.cookiejar import CookieJar
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener

from ..models import Alert, Geometry, TropicalProduct, TropicalSystem
from ..sources import WarningSource
from .base import DEFAULT_TIMEOUT, DEFAULT_USER_AGENT, BackendError, WarningBackend

_SESSION_URL = 'https://meteofrance.re/fr/cyclone'
_API_ROOT = 'https://rwg.meteofrance.com/internet2018client/2.0/cyclone'


class MeteoFranceReunionTropicalBackend(WarningBackend):
    """Fetch current Southwest Indian Ocean systems from Météo-France RSMC data."""

    backend_id = 'meteofrance_reunion_tropical'

    def fetch_alerts(
        self,
        source: WarningSource,
        *,
        lat: float | None = None,
        lon: float | None = None,
        lang: str | None = None,
        debug: bool = False,
    ) -> list[Alert]:
        """Return no ordinary alerts for the RSMC cyclone product."""
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
        """Fetch the current seasonal cyclone list and its trajectories."""
        del lat, lon, lang
        try:
            payloads = _fetch_current_reunion_payloads(season=_current_season(), debug=debug)
        except BackendError:
            return []

        systems = [
            system
            for listing, trajectory in payloads
            if (system := _parse_reunion_system(listing, trajectory, source=source.id, url=source.url)) is not None
        ]
        return sorted(systems, key=lambda system: (system.name.casefold(), system.id))

    def fetch_tropical_products(
        self,
        source: WarningSource,
        system: TropicalSystem,
        *,
        debug: bool = False,
    ) -> list[TropicalProduct]:
        """Fetch detailed RSMC analysis and forecast trajectory data lazily."""
        try:
            payload = _fetch_reunion_trajectory(system.id, debug=debug)
        except BackendError:
            return []
        trajectory = payload.get('cyclone_trajectory')
        if not isinstance(trajectory, dict) or _text(trajectory.get('cyclone_id')) != system.id:
            return []

        products: list[TropicalProduct] = []
        analysis = _reunion_analysis_product_data(trajectory)
        if analysis is not None:
            products.append(
                TropicalProduct(
                    kind='analysis',
                    label='Analysis',
                    title=f'{system.name} Analysis',
                    issued_at=system.issued_at,
                    url=source.url,
                    data=analysis,
                )
            )
        forecast = _reunion_forecast_product_data(trajectory)
        if forecast is not None:
            products.append(
                TropicalProduct(
                    kind='forecast',
                    label='Forecast',
                    title=f'{system.name} Forecast',
                    issued_at=system.issued_at,
                    url=source.url,
                    data=forecast,
                )
            )
        return products


def _current_season(now: datetime | None = None) -> str:
    """Return the Southwest Indian Ocean season identifier used by Météo-France."""
    current = now or datetime.now(UTC)
    if current.month <= 6:
        return f'{current.year - 1}{current.year}'
    return f'{current.year}{current.year + 1}'


def _fetch_current_reunion_payloads(*, season: str, debug: bool) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Return current cyclone-list rows paired with their trajectory documents."""
    cookies = CookieJar()
    opener = build_opener(HTTPCookieProcessor(cookies))
    _prime_meteofrance_session(opener, debug=debug)
    token = _session_token(cookies)
    if token is None:
        raise BackendError('Météo-France did not provide an anonymous session token')

    listing = _fetch_meteofrance_json(
        opener,
        token,
        'list',
        params={'basin': 'SWI', 'season': season, 'current': 'current'},
        debug=debug,
    )
    entries = _current_cyclone_entries(listing)
    payloads: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for entry in entries:
        cyclone_id = _text(entry.get('cyclone_id'))
        if cyclone_id is None:
            continue
        try:
            trajectory = _fetch_meteofrance_json(
                opener,
                token,
                'trajectory',
                params={'cyclone_id': cyclone_id},
                debug=debug,
            )
        except BackendError:
            continue
        payloads.append((entry, trajectory))
    return payloads


def _fetch_reunion_trajectory(cyclone_id: str, *, debug: bool) -> dict[str, Any]:
    """Fetch one selected trajectory without re-fetching every active system."""
    cookies = CookieJar()
    opener = build_opener(HTTPCookieProcessor(cookies))
    _prime_meteofrance_session(opener, debug=debug)
    token = _session_token(cookies)
    if token is None:
        raise BackendError('Météo-France did not provide an anonymous session token')
    return _fetch_meteofrance_json(
        opener,
        token,
        'trajectory',
        params={'cyclone_id': cyclone_id},
        debug=debug,
    )


def _prime_meteofrance_session(opener: Any, *, debug: bool) -> None:
    request = Request(_SESSION_URL, headers={'User-Agent': DEFAULT_USER_AGENT})
    try:
        with opener.open(request, timeout=DEFAULT_TIMEOUT) as response:
            response.read()
    except (HTTPError, URLError, OSError, TimeoutError) as exc:
        if debug:
            logging.error('Météo-France session request failed: %s', exc)
        raise BackendError(str(exc)) from exc


def _session_token(cookies: CookieJar) -> str | None:
    for cookie in cookies:
        if cookie.name == 'mfsession' and cookie.value:
            return codecs.decode(cookie.value, 'rot_13')
    return None


def _fetch_meteofrance_json(
    opener: Any,
    token: str,
    resource: str,
    *,
    params: dict[str, str],
    debug: bool,
) -> dict[str, Any]:
    url = f'{_API_ROOT}/{resource}?{urlencode(params)}'
    request = Request(
        url,
        headers={
            'User-Agent': DEFAULT_USER_AGENT,
            'Accept': 'application/json',
            'Authorization': f'Bearer {token}',
        },
    )
    try:
        with opener.open(request, timeout=DEFAULT_TIMEOUT) as response:
            payload = response.read().decode(response.headers.get_content_charset() or 'utf-8', errors='replace')
    except (HTTPError, URLError, OSError, TimeoutError) as exc:
        if debug:
            logging.error('Météo-France API request failed for %r: %s', url, exc)
        raise BackendError(str(exc)) from exc
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise BackendError('Invalid Météo-France cyclone JSON response') from exc
    if not isinstance(data, dict):
        raise BackendError('Unexpected Météo-France cyclone JSON response')
    return data


def _current_cyclone_entries(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize the one-or-many shapes returned by the current list endpoint."""
    value = payload.get('cyclone_list')
    if isinstance(value, dict):
        if isinstance(value.get('cyclone_id'), str):
            return [value]
        return [entry for entry in value.values() if isinstance(entry, dict)]
    if isinstance(value, list):
        return [entry for entry in value if isinstance(entry, dict)]
    return []


def _parse_reunion_system(
    listing: dict[str, Any],
    trajectory_payload: dict[str, Any],
    *,
    source: str,
    url: str | None,
) -> TropicalSystem | None:
    """Normalize one Météo-France trajectory into the public storm model."""
    trajectory = trajectory_payload.get('cyclone_trajectory')
    if not isinstance(trajectory, dict):
        return None

    system_id = _text(trajectory.get('cyclone_id')) or _text(listing.get('cyclone_id'))
    name = _text(trajectory.get('cyclone_name')) or _text(listing.get('cyclone_name'))
    if system_id is None or name is None:
        return None

    analysis = _latest_analysis_feature(trajectory)
    properties = analysis.get('properties') if isinstance(analysis, dict) else None
    if not isinstance(properties, dict):
        properties = {}
    cyclone_data = properties.get('cyclone_data')
    if not isinstance(cyclone_data, dict):
        cyclone_data = {}
    center_lat, center_lon = _feature_coordinates(analysis)

    development = _text(cyclone_data.get('development'))
    classification = _display_development(development) or 'Tropical Cyclone'
    reference_time = _text(trajectory.get('reference_time')) or _text(listing.get('reference_time'))
    parameters: dict[str, list[str]] = {
        'Météo-France Cyclone ID': [system_id],
    }
    season = trajectory.get('season') or listing.get('season')
    if season is not None:
        parameters['Météo-France Season'] = [str(season)]
    if reference_time:
        parameters['Météo-France Reference Time'] = [reference_time]
    update_time = _text(trajectory.get('update_time'))
    if update_time:
        parameters['Météo-France Update Time'] = [update_time]
    accuracy = properties.get('position_accuracy')
    if isinstance(accuracy, (int, float)):
        parameters['Météo-France Position Accuracy'] = [f'{accuracy:g} km']
    wind_contours = cyclone_data.get('wind_contours')
    if isinstance(wind_contours, (list, dict)):
        parameters['Météo-France Wind Contours'] = [json.dumps(wind_contours, separators=(',', ':'))]
    forecast_peak = _forecast_peak_information(trajectory)
    if forecast_peak:
        parameters['Météo-France Forecast Peak'] = [forecast_peak]

    return TropicalSystem(
        id=system_id,
        source=source,
        classification=classification,
        name=name,
        headline=f'{classification}: {name}',
        basin='Southwest Indian Ocean',
        url=url,
        issued_at=WarningBackend.parse_datetime(reference_time),
        center_lat=center_lat,
        center_lon=center_lon,
        movement=_movement(cyclone_data),
        min_pressure=_measurement(cyclone_data.get('minimum_pressure'), 'hPa'),
        max_wind=_maximum_wind(cyclone_data.get('maximum_wind')),
        summary=f'Météo-France La Réunion RSMC tropical cyclone trajectory for {name}.',
        data_urls={'official_page': url} if url else {},
        geometries=_trajectory_geometry(trajectory),
        parameters=parameters,
    )


def _latest_analysis_feature(trajectory: dict[str, Any]) -> dict[str, Any] | None:
    candidates = [
        feature
        for feature in trajectory.get('features', [])
        if isinstance(feature, dict)
        and isinstance(feature.get('properties'), dict)
        and feature['properties'].get('data_type') == 'analysis'
        and _feature_coordinates(feature) != (None, None)
    ]
    if not candidates:
        return None
    latest = candidates[0]
    latest_time = WarningBackend.parse_datetime(latest['properties'].get('time'))
    for candidate in candidates[1:]:
        candidate_time = WarningBackend.parse_datetime(candidate['properties'].get('time'))
        if candidate_time is not None and (latest_time is None or candidate_time > latest_time):
            latest = candidate
            latest_time = candidate_time
    return latest


def _feature_coordinates(feature: dict[str, Any] | None) -> tuple[float | None, float | None]:
    if not isinstance(feature, dict):
        return None, None
    geometry = feature.get('geometry')
    if not isinstance(geometry, dict) or geometry.get('type') != 'Point':
        return None, None
    coordinates = geometry.get('coordinates')
    if not isinstance(coordinates, list) or len(coordinates) < 2:
        return None, None
    lon, lat = coordinates[:2]
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        return None, None
    return float(lat), float(lon)


def _trajectory_geometry(trajectory: dict[str, Any]) -> dict[str, Geometry]:
    points: list[list[float]] = []
    for feature in trajectory.get('features', []):
        lat, lon = _feature_coordinates(feature if isinstance(feature, dict) else None)
        if lat is not None and lon is not None:
            points.append([lon, lat])
    if len(points) < 2:
        return {}
    return {'track': {'type': 'LineString', 'coordinates': points}}


def _reunion_analysis_product_data(trajectory: dict[str, Any]) -> dict[str, Any] | None:
    feature = _latest_analysis_feature(trajectory)
    return _reunion_feature_data(feature) if feature is not None else None


def _reunion_forecast_product_data(trajectory: dict[str, Any]) -> dict[str, Any] | None:
    points = [
        data
        for feature in trajectory.get('features', [])
        if isinstance(feature, dict)
        and isinstance(feature.get('properties'), dict)
        and feature['properties'].get('data_type') == 'forecast'
        if (data := _reunion_feature_data(feature)) is not None
    ]
    return {'points': points} if points else None


def _reunion_feature_data(feature: dict[str, Any]) -> dict[str, Any] | None:
    properties = feature.get('properties')
    latitude, longitude = _feature_coordinates(feature)
    if not isinstance(properties, dict) or latitude is None or longitude is None:
        return None
    data: dict[str, Any] = {
        'latitude': latitude,
        'longitude': longitude,
    }
    for key in ('time', 'data_type', 'position_accuracy', 'cyclone_data'):
        value = properties.get(key)
        if value is not None:
            data[key] = value
    return data


def _forecast_peak_information(trajectory: dict[str, Any]) -> str | None:
    """Return a compact maximum-wind forecast summary, when one is published."""
    peak: tuple[float, str | None, str | None, str | None] | None = None
    for feature in trajectory.get('features', []):
        if not isinstance(feature, dict):
            continue
        properties = feature.get('properties')
        if not isinstance(properties, dict) or properties.get('data_type') != 'forecast':
            continue
        cyclone_data = properties.get('cyclone_data')
        if not isinstance(cyclone_data, dict):
            continue
        maximum_wind = cyclone_data.get('maximum_wind')
        speed = maximum_wind.get('wind_speed_kt') if isinstance(maximum_wind, dict) else None
        if not isinstance(speed, (int, float)):
            continue
        candidate = (
            float(speed),
            _display_development(_text(cyclone_data.get('development'))),
            _maximum_wind(maximum_wind),
            _text(properties.get('time')),
        )
        if peak is None or candidate[0] > peak[0]:
            peak = candidate
    if peak is None:
        return None
    _, classification, wind, time = peak
    details = ', '.join(detail for detail in (classification, wind) if detail)
    return f'{details} at {time}' if time else details or None


def _display_development(value: str | None) -> str | None:
    if not value:
        return None
    return value.replace('_', ' ').replace('-', ' ').title()


def _movement(cyclone_data: dict[str, Any]) -> str | None:
    motion = cyclone_data.get('storm_motion')
    if not isinstance(motion, dict):
        return None
    speed = _measurement(motion.get('speed_kt'), 'kt')
    direction = motion.get('direction_toward')
    if isinstance(direction, (int, float)):
        direction_text = f'toward {direction:g}°'
        return f'{speed} {direction_text}' if speed else direction_text
    return speed


def _maximum_wind(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    speed = _measurement(value.get('wind_speed_kt'), 'kt')
    gust = _measurement(value.get('wind_speed_gust_kt'), 'kt')
    if speed and gust:
        return f'{speed} (gust {gust})'
    return speed or gust


def _measurement(value: Any, unit: str) -> str | None:
    if not isinstance(value, (int, float)):
        return None
    return f'{value:g} {unit}'


def _text(value: Any) -> str | None:
    return WarningBackend.text_or_none(value)
