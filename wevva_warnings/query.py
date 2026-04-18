"""High-level query API."""

from __future__ import annotations

import logging
import warnings
from datetime import UTC, datetime

from ._debug import emit_progress
from .geocoding import resolve_alert_geometry
from .geometry import point_in_geometry
from .models import Alert
from .registry import LanguageNotSupportedError, get_backend, get_source, get_sources_for_country


def get_alerts_for_point(
    lat: float,
    lon: float,
    country_code: str,
    lang: str | None = None,
    debug: bool = False,
    active_only: bool = False,
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
        If True, emit progress information about the query process.
    active_only : bool, optional
        If True, only return alerts that are currently active. This is
        determined by comparing the current UTC time to each alert's start and
        end times.

    Returns
    -------
    list[Alert]
        A list of alerts that apply to the given point.

    """
    alerts: list[Alert] = []
    seen: set[tuple[str, str]] = set()
    normalized_country = country_code.strip().upper()
    selected_lang = lang
    try:
        sources = get_sources_for_country(normalized_country, lang=selected_lang)
    except LanguageNotSupportedError as exc:
        message = (
            f'Language {exc.lang!r} is not supported for country code {exc.country_code!r}; '
            'falling back to the default source selection.'
        )
        warnings.warn(message, stacklevel=2)
        if debug:
            logging.warning(message)
        selected_lang = None
        sources = get_sources_for_country(normalized_country, lang=None)
    source_backends = [(source, backend) for source in sources if (backend := get_backend(source)) is not None]
    now = _utc_now() if active_only else None

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
        emit_progress('sources_total', total=len(source_backends))

    for source, backend in source_backends:
        if debug:
            emit_progress('source_started', source=source.id)
            logging.info('Using provider %r via %s()', source.id, backend.__class__.__name__)

        source_alerts = backend.fetch_alerts(source, lat=lat, lon=lon, lang=selected_lang, debug=debug)
        matched_count = 0
        missing_geometry = 0
        inactive_skipped = 0

        for alert in source_alerts:
            if not backend.uses_native_point_query:
                geometry = _resolved_alert_geometry(alert)
                if geometry is None:
                    missing_geometry += 1
                    continue
                if not point_in_geometry(lat, lon, geometry):
                    continue

            if active_only and now is not None and not alert.is_active(now):
                inactive_skipped += 1
                continue

            matched_count += 1
            key = (alert.source, alert.id)
            if key in seen:
                continue
            seen.add(key)
            alerts.append(alert)

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
            emit_progress('source_finished', source=source.id)

    if debug:
        logging.info('Returning %s warnings', len(alerts))
        for alert in alerts:
            logging.info(alert)

    return alerts


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


def _utc_now() -> datetime:
    """Return the current UTC time.

    Returns
    -------
    datetime
        The current time in UTC.

    """
    return datetime.now(UTC)


def _resolved_alert_geometry(alert: Alert) -> dict[str, object] | None:
    """Return alert geometry, populating it from geocodes when possible."""
    if alert.geometry is not None:
        return alert.geometry
    geometry = resolve_alert_geometry(alert)
    if geometry is not None:
        alert.geometry = geometry
    return geometry
