"""High-level query API."""

from __future__ import annotations

import logging
import math
import warnings
from collections.abc import Iterable
from datetime import UTC, datetime

from ._debug import bind_progress_callback, emit_progress
from .geocoding import resolve_alert_geometry
from .geometry import point_in_geometry
from .models import Alert, TropicalSystem
from .progress import WarningQueryProgress
from .registry import LanguageNotSupportedError, get_backend, get_source, get_sources_for_country, list_tropical_sources
from .sources import WarningSource


def get_alerts_for_point(
    lat: float,
    lon: float,
    country_code: str,
    lang: str | None = None,
    debug: bool = False,
    active_only: bool = False,
    progress: WarningQueryProgress | None = None,
) -> list[Alert]:
    """Return alerts that apply to one point.

    Finds all sources that cover the given country, queries them for alerts,
    and filters them to those that apply to the given point.

    Parameters
    ----------
    lat : float
        Latitude of the point to query.
    lon : float
        Longitude of the point to query.
    country_code : str
        ISO 3166-1 alpha-2 country code to filter sources by.
    lang : str | None, optional
        Optional language code used to filter sources. If not provided,
        English-capable sources are preferred when available. If the requested
        language is not supported for the country, a warning is emitted and the
        default source selection is used instead.
    debug : bool, optional
        If True, emit diagnostic logging about the query process.
    active_only : bool, optional
        If True, only return alerts that are currently active. This is
        determined by comparing the current UTC time to each alert's start and
        end times.
    progress : WarningQueryProgress | None, optional
        Callback invoked with documented progress events while the query runs.
        It is called synchronously on the calling thread; callback exceptions
        are ignored and cannot affect the query result.

    Returns
    -------
    list[Alert]
        A list of alerts that apply to the given point.

    """
    if progress is None:
        return _get_alerts_for_point(
            lat,
            lon,
            country_code,
            lang=lang,
            debug=debug,
            active_only=active_only,
        )

    with bind_progress_callback(progress):
        return _get_alerts_for_point(
            lat,
            lon,
            country_code,
            lang=lang,
            debug=debug,
            active_only=active_only,
        )


def _get_alerts_for_point(
    lat: float,
    lon: float,
    country_code: str,
    *,
    lang: str | None,
    debug: bool,
    active_only: bool,
    uses_native_point_query: bool | None = None,
) -> list[Alert]:
    """Implement one point query with any active progress callback."""
    alerts: list[Alert] = []
    seen: set[tuple[str, str]] = set()
    normalized_country = country_code.strip().upper()
    emit_progress('query_started', country_code=normalized_country, lat=lat, lon=lon)
    sources, selected_lang = _select_alert_sources_for_country(country_code, lang=lang, debug=debug)
    source_backends = _source_backends(sources, uses_native_point_query=uses_native_point_query)
    now = _utc_now() if active_only else None

    emit_progress('sources_total', total=len(source_backends))
    if debug:
        logging.info(
            'Looking up warnings for point (%s, %s) in country %r',
            f'{lat:.4f}',
            f'{lon:.4f}',
            normalized_country,
        )
        logging.info('Available providers: %s', [source.id for source, _ in source_backends])
        if active_only:
            logging.info('Only alerts that are active right now will be returned.')
    for source, backend in source_backends:
        provider_name = getattr(source, 'name', source.id)
        emit_progress('source_started', source=source.id, provider_name=provider_name)
        if debug:
            logging.info('Using provider %r via %s()', source.id, backend.__class__.__name__)

        source_alerts = backend.fetch_alerts(source, lat=lat, lon=lon, lang=selected_lang, debug=debug)
        _attach_alert_source_info(source_alerts, source)
        total_candidates = len(source_alerts)
        emit_progress('alerts_total', source=source.id, total=total_candidates, phase='matching')
        matched_count = 0
        missing_geometry = 0
        inactive_skipped = 0

        for completed, alert in enumerate(source_alerts, start=1):
            matches_point = True
            if not backend.uses_native_point_query:
                matches_point, geometry_missing = _alert_geometry_matches_point(alert, lat=lat, lon=lon)
                if geometry_missing:
                    missing_geometry += 1

            if matches_point:
                is_active = not active_only or now is None or alert.is_active(now)
                if not is_active:
                    inactive_skipped += 1
                else:
                    matched_count += 1
                    key = (alert.source, alert.id)
                    if key not in seen:
                        seen.add(key)
                        alerts.append(alert)

            emit_progress(
                'alerts_checked',
                source=source.id,
                completed=completed,
                total=total_candidates,
                matched=matched_count,
                phase='matching',
            )

        if debug:
            if backend.uses_native_point_query:
                message = f'Provider {source.id!r} returned {len(source_alerts) - inactive_skipped} warnings from its point query'
            else:
                message = f'Provider {source.id!r} matched {matched_count} of {len(source_alerts)} warnings to the query point'

            details: list[str] = []
            if inactive_skipped:
                details.append(f'filtered {inactive_skipped} that are not active now')
            if missing_geometry:
                details.append(f'skipped {missing_geometry} without geometry')
            if details:
                message = f'{message}, ' + ', '.join(details)

            logging.info('%s.', message)
        emit_progress(
            'source_finished',
            source=source.id,
            candidates=total_candidates,
            matched=matched_count,
            skipped_without_geometry=missing_geometry,
            inactive_filtered=inactive_skipped,
        )

    deduped_alerts = deduplicate_alerts(alerts)

    if debug:
        if len(deduped_alerts) != len(alerts):
            logging.info(
                'Deduped %s semantically identical point-query warnings.',
                len(alerts) - len(deduped_alerts),
            )
        logging.info('Returning %s warnings', len(deduped_alerts))
        for alert in deduped_alerts:
            logging.info(alert)

    emit_progress('finished', alert_count=len(deduped_alerts))
    return deduped_alerts


def get_alert_sources_for_country(
    country_code: str,
    *,
    lang: str | None = None,
) -> list[WarningSource]:
    """Return alert sources selected for a country and language request.

    This applies the same country normalization, default English preference,
    and unsupported-language fallback as :func:`get_alerts_for_point`.
    """
    sources, _ = _select_alert_sources_for_country(country_code, lang=lang, debug=False)
    return sources


def get_alerts_for_country(
    country_code: str,
    *,
    lang: str | None = None,
    active_only: bool = False,
    progress: WarningQueryProgress | None = None,
) -> list[Alert]:
    """Return country-level alert candidates for one country.

    This fetches the country-level products of the sources selected for the
    request, without applying a point filter. It retains its original broad
    behaviour and includes native point-query sources; use
    :func:`get_reusable_alerts_for_country` when candidates will be cached for
    repeated local calls to :func:`match_alerts_to_point`.

    ``progress`` uses the documented country-query events and is called
    synchronously. Callback exceptions are ignored.
    """
    if progress is None:
        return _get_alerts_for_country(country_code, lang=lang, active_only=active_only)

    with bind_progress_callback(progress):
        return _get_alerts_for_country(country_code, lang=lang, active_only=active_only)


def get_reusable_alerts_for_country(
    country_code: str,
    *,
    lang: str | None = None,
    active_only: bool = False,
    progress: WarningQueryProgress | None = None,
) -> list[Alert]:
    """Return country candidates that are safe to cache for local matching.

    Only sources whose backends do not use native point queries are fetched.
    The returned alerts can be passed to :func:`match_alerts_to_point` for one
    or more locations. Native point-query results are deliberately excluded;
    retrieve those for each location with :func:`get_native_alerts_for_point`.

    ``progress`` uses the documented country-query events and is called
    synchronously. Callback exceptions are ignored.
    """
    if progress is None:
        return _get_alerts_for_country(
            country_code,
            lang=lang,
            active_only=active_only,
            uses_native_point_query=False,
        )

    with bind_progress_callback(progress):
        return _get_alerts_for_country(
            country_code,
            lang=lang,
            active_only=active_only,
            uses_native_point_query=False,
        )


def get_native_alerts_for_point(
    lat: float,
    lon: float,
    country_code: str,
    lang: str | None = None,
    debug: bool = False,
    active_only: bool = False,
    progress: WarningQueryProgress | None = None,
) -> list[Alert]:
    """Return alerts from only the selected native point-query sources.

    This sends ``lat`` and ``lon`` only to sources whose backend declares
    ``uses_native_point_query = True``. It is intended to complement cached
    results from :func:`get_reusable_alerts_for_country`; use
    :func:`deduplicate_alerts` after combining the two result lists.

    ``progress`` uses the same point-query event contract as
    :func:`get_alerts_for_point`. Callback exceptions are ignored.
    """
    if progress is None:
        return _get_alerts_for_point(
            lat,
            lon,
            country_code,
            lang=lang,
            debug=debug,
            active_only=active_only,
            uses_native_point_query=True,
        )

    with bind_progress_callback(progress):
        return _get_alerts_for_point(
            lat,
            lon,
            country_code,
            lang=lang,
            debug=debug,
            active_only=active_only,
            uses_native_point_query=True,
        )


def _get_alerts_for_country(
    country_code: str,
    *,
    lang: str | None,
    active_only: bool,
    uses_native_point_query: bool | None = None,
) -> list[Alert]:
    """Implement one country candidate query with any active progress callback."""
    normalized_country = country_code.strip().upper()
    emit_progress('country_query_started', country_code=normalized_country)
    sources, selected_lang = _select_alert_sources_for_country(country_code, lang=lang, debug=False)
    source_backends = _source_backends(sources, uses_native_point_query=uses_native_point_query)
    now = _utc_now() if active_only else None
    candidates: list[Alert] = []

    emit_progress('sources_total', total=len(source_backends))
    for source, backend in source_backends:
        emit_progress('source_started', source=source.id, provider_name=source.name)
        source_alerts = backend.fetch_alerts(source, lang=selected_lang, debug=False)
        _attach_alert_source_info(source_alerts, source)

        source_candidates: list[Alert] = []
        seen: set[tuple[str, str]] = set()
        inactive_filtered = 0
        for alert in source_alerts:
            _resolved_alert_geometry(alert)
            if active_only and now is not None and not alert.is_active(now):
                inactive_filtered += 1
                continue
            key = (alert.source, alert.id)
            if key in seen:
                continue
            seen.add(key)
            source_candidates.append(alert)

        candidates.extend(source_candidates)
        emit_progress(
            'country_source_finished',
            source=source.id,
            candidates=len(source_candidates),
            inactive_filtered=inactive_filtered,
        )

    emit_progress('country_finished', alert_count=len(candidates))
    return candidates


def match_alerts_to_point(
    alerts: list[Alert],
    *,
    lat: float,
    lon: float,
    active_only: bool = False,
) -> list[Alert]:
    """Return supplied alert candidates whose geometry contains one point.

    Matching is local and makes no network calls. Missing geometry is resolved
    from supported packaged geocodes where possible, which may populate the
    ``geometry`` field on the supplied alert objects.
    """
    now = _utc_now() if active_only else None
    matches: list[Alert] = []
    seen: set[tuple[str, str]] = set()

    for alert in alerts:
        matches_point, _ = _alert_geometry_matches_point(alert, lat=lat, lon=lon)
        if not matches_point:
            continue
        if active_only and now is not None and not alert.is_active(now):
            continue
        key = (alert.source, alert.id)
        if key in seen:
            continue
        seen.add(key)
        matches.append(alert)

    return deduplicate_alerts(matches)


def deduplicate_alerts(alerts: Iterable[Alert]) -> list[Alert]:
    """Return alerts with point-query source and semantic duplicates removed.

    This is useful after combining locally matched reusable candidates with
    native point-query results. The input is not modified.
    """
    unique_ids: list[Alert] = []
    seen_ids: set[tuple[str, str]] = set()
    for alert in alerts:
        key = (alert.source, alert.id)
        if key in seen_ids:
            continue
        seen_ids.add(key)
        unique_ids.append(alert)
    return _dedupe_point_alerts(unique_ids)


def get_alerts_for_source(
    source_id: str,
    *,
    debug: bool = False,
    active_only: bool = False,
) -> list[Alert]:
    """Return alerts from one source.

    Parameters
    ----------
    source_id : str
        Identifier of the source to query.
    debug : bool, optional
        If True, emit progress information about the query process.
    active_only : bool, optional
        If True, only return alerts that are currently active.

    Returns
    -------
    list[Alert]
        A list of alerts returned by the requested source. If the source is
        unknown or has no backend, an empty list is returned.

    """
    source = get_source(source_id)
    if source is None:
        return []

    backend = get_backend(source)
    if backend is None:
        return []

    if debug:
        logging.info('Using provider %r via %s()', source.id, backend.__class__.__name__)

    alerts = backend.fetch_alerts(source, debug=debug)
    _attach_alert_source_info(alerts, source)
    now = _utc_now() if active_only else None
    deduped: list[Alert] = []
    seen: set[tuple[str, str]] = set()
    inactive_skipped = 0
    for alert in alerts:
        _resolved_alert_geometry(alert)
        if active_only and now is not None and not alert.is_active(now):
            inactive_skipped += 1
            continue
        key = (alert.source, alert.id)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(alert)

    if debug:
        message = f'Provider {source.id!r} is returning {len(deduped)} warnings'
        if active_only and inactive_skipped:
            message = f'{message} and filtered {inactive_skipped} that are not active now'
        logging.info('%s.', message)

        for alert in deduped:
            logging.info(alert)

    return deduped


def get_swic_extreme_alerts(
    *,
    active_only: bool = True,
    include_marine: bool = False,
    debug: bool = False,
) -> list[Alert]:
    """Return mapped Extreme-warning candidates from WMO SWIC.

    This global discovery helper is deliberately separate from country and
    point routing. It returns one alert per SWIC CAP URL with the map's
    polygonal geometry. Results cover only warnings currently represented by
    the WMO Severe Weather Information Centre, not every warning worldwide.

    ``active_only`` defaults to ``True`` and is evaluated locally with
    :meth:`Alert.is_active`. Marine warnings are excluded by default; pass
    ``include_marine=True`` to include SWIC rows marked as marine.
    """
    source = get_source('swic_extreme')
    if source is None:
        return []
    backend = get_backend(source)
    if backend is None:
        return []

    alerts = backend.fetch_alerts(source, debug=debug, include_marine=include_marine)
    _attach_alert_source_info(alerts, source)
    if not active_only:
        return alerts

    now = _utc_now()
    return [alert for alert in alerts if alert.is_active(now)]


def get_tropical_systems_for_source(
    source_id: str,
    *,
    debug: bool = False,
) -> list[TropicalSystem]:
    """Return tropical systems from one tropical-system source."""
    source = get_source(source_id)
    if source is None or source.kind != 'tropical_system':
        return []

    backend = get_backend(source)
    if backend is None:
        return []

    if debug:
        logging.info('Using tropical-system provider %r via %s()', source.id, backend.__class__.__name__)

    systems = backend.fetch_tropical_systems(source, debug=debug)
    _attach_tropical_source_info(systems, source)

    if debug:
        logging.info('Provider %r is returning %s tropical systems.', source.id, len(systems))
        for system in systems:
            logging.info(system)

    return systems


def get_tropical_systems_near(
    lat: float,
    lon: float,
    *,
    radius_km: float = 1000.0,
    source_ids: list[str] | None = None,
    debug: bool = False,
) -> list[TropicalSystem]:
    """Return tropical systems near one point.

    A system matches when its center is within ``radius_km`` of the point, or
    when the point lies inside one of the system's polygonal geometry layers
    such as a cone or watch/warning area.
    """
    if radius_km < 0:
        raise ValueError('radius_km must be non-negative.')

    sources = _tropical_sources_for_query(source_ids)
    if debug:
        logging.info(
            'Looking up tropical systems near (%s, %s) within %.1f km.',
            f'{lat:.4f}',
            f'{lon:.4f}',
            radius_km,
        )
        logging.info('Available tropical providers: %s', [source.id for source in sources])

    matches: list[TropicalSystem] = []
    seen: set[tuple[str, str]] = set()
    for source in sources:
        backend = get_backend(source)
        if backend is None:
            continue

        if debug:
            logging.info('Using tropical-system provider %r via %s()', source.id, backend.__class__.__name__)

        systems = backend.fetch_tropical_systems(source, lat=lat, lon=lon, debug=debug)
        _attach_tropical_source_info(systems, source)
        matched_count = 0
        for system in systems:
            if not _tropical_system_matches_point(system, lat=lat, lon=lon, radius_km=radius_km):
                continue
            matched_count += 1
            key = (system.source, system.id)
            if key in seen:
                continue
            seen.add(key)
            matches.append(system)

        if debug:
            logging.info('Provider %r matched %s of %s tropical systems.', source.id, matched_count, len(systems))

    if debug:
        logging.info('Returning %s tropical systems.', len(matches))
        for system in matches:
            logging.info(system)

    return matches


def _utc_now() -> datetime:
    """Return the current UTC time.

    Returns
    -------
    datetime
        The current time in UTC.

    """
    return datetime.now(UTC)


def _select_alert_sources_for_country(
    country_code: str,
    *,
    lang: str | None,
    debug: bool,
) -> tuple[list[WarningSource], str | None]:
    """Select country alert sources, with the public fallback behaviour."""
    normalized_country = country_code.strip().upper()
    try:
        return get_sources_for_country(normalized_country, lang=lang), lang
    except LanguageNotSupportedError as exc:
        message = (
            f'Language {exc.lang!r} is not supported for country code {exc.country_code!r}; '
            'falling back to the default source selection.'
        )
        warnings.warn(message, stacklevel=3)
        if debug:
            logging.warning(message)
        return get_sources_for_country(normalized_country, lang=None), None


def _source_backends(
    sources: list[WarningSource],
    *,
    uses_native_point_query: bool | None = None,
) -> list[tuple[WarningSource, object]]:
    """Return available backends, optionally filtered by point-query capability."""
    source_backends: list[tuple[WarningSource, object]] = []
    for source in sources:
        backend = get_backend(source)
        if backend is None:
            continue
        if (
            uses_native_point_query is not None
            and bool(getattr(backend, 'uses_native_point_query', False)) != uses_native_point_query
        ):
            continue
        source_backends.append((source, backend))
    return source_backends


def _alert_geometry_matches_point(
    alert: Alert,
    *,
    lat: float,
    lon: float,
) -> tuple[bool, bool]:
    """Return whether an alert matches locally and whether geometry was missing."""
    geometry = _resolved_alert_geometry(alert)
    if geometry is None:
        return False, True
    return point_in_geometry(lat, lon, geometry), False


def _resolved_alert_geometry(alert: Alert) -> dict[str, object] | None:
    """Return alert geometry, populating it from geocodes when possible."""
    if alert.geometry is not None:
        return alert.geometry
    geometry = resolve_alert_geometry(alert)
    if geometry is not None:
        alert.geometry = geometry
    return geometry


def _attach_alert_source_info(alerts: list[Alert], source: WarningSource) -> None:
    """Attach source metadata to alerts returned through the public query API."""
    for alert in alerts:
        alert.source_info = source


def _attach_tropical_source_info(systems: list[TropicalSystem], source: WarningSource) -> None:
    """Attach source metadata to tropical systems returned through the public query API."""
    for system in systems:
        system.source_info = source


def _tropical_sources_for_query(source_ids: list[str] | None) -> list[WarningSource]:
    if source_ids is None:
        return list_tropical_sources()

    sources: list[WarningSource] = []
    seen: set[str] = set()
    for source_id in source_ids:
        source = get_source(source_id)
        if source is None or source.kind != 'tropical_system' or source.id in seen:
            continue
        seen.add(source.id)
        sources.append(source)
    return sources


def _tropical_system_matches_point(
    system: TropicalSystem,
    *,
    lat: float,
    lon: float,
    radius_km: float,
) -> bool:
    if system.center_lat is not None and system.center_lon is not None:
        if _haversine_km(lat, lon, system.center_lat, system.center_lon) <= radius_km:
            return True

    for geometry in system.geometries.values():
        if point_in_geometry(lat, lon, geometry):
            return True

    return False


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance between two WGS84 points."""
    radius = 6371.0088
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _dedupe_point_alerts(alerts: list[Alert]) -> list[Alert]:
    """Collapse semantically duplicate point-query alerts.

    Point queries can match multiple overlapping upstream warning regions that
    differ only in internal identifiers while presenting identical user-facing
    warning content. Keep source-level `id` dedupe in `get_alerts_for_source`,
    but collapse those duplicates for point-query results.
    """
    deduped: list[Alert] = []
    seen: set[tuple[object, ...]] = set()
    for alert in alerts:
        key = (
            alert.source,
            alert.headline,
            alert.event,
            alert.severity,
            alert.onset.isoformat() if alert.onset else None,
            alert.expires.isoformat() if alert.expires else None,
            alert.description,
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(alert)
    return deduped
