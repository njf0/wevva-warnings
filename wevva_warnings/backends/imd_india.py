"""India Meteorological Department warning ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta, timezone
from email.utils import parsedate_to_datetime
import logging
import re
from typing import Any
from urllib.parse import parse_qs, urlparse
from xml.etree import ElementTree

from .._debug import emit_progress
from ..cap import _parse_cap_polygon, _rings_to_geometry, parse_cap_alert
from ..models import Alert
from ..sources import WarningSource
from ._cap_feed import CAP_ACCEPT, absolute_url, child_text, fetch_feed_root, local_name
from .base import BackendError, ETagCachingSession, WarningBackend, fetch_json, fetch_text


SACHET_RSS_URL = 'https://sachet.ndma.gov.in/cap_public_website/rss/rss_india.xml'
IMD_NOWCAST_WFS_URL = 'https://reactjs.imd.gov.in/geoserver/imd/wfs'
IMD_NOWCAST_MAP_URL = 'https://mausam.imd.gov.in/responsive/districtWiseNowcastGIS.php'
_SACHET_HOST = 'sachet.ndma.gov.in'
_SACHET_CAP_PATH = '/cap_public_website/FetchXMLFile'
_SACHET_POLYGON_PATH = '/cap_public_website/FetchPolygonXMLFile'
_IMD_SENDER_RE = re.compile(r'^(?:imd(?:[-_\s]|$)|india meteorological department)', re.IGNORECASE)
_INDIA_TIME = timezone(timedelta(hours=5, minutes=30))
_NOWCAST_CATEGORIES = {
    2: 'Light rain',
    3: 'Light snow',
    4: 'Light thunderstorms with surface wind below 40 km/h',
    5: 'Slight dust storm',
    6: 'Low probability of lightning',
    7: 'Moderate rain',
    8: 'Moderate snow',
    9: 'Moderate thunderstorms with surface wind 41–61 km/h',
    10: 'Moderate dust storm',
    11: 'Moderate probability of lightning',
    12: 'Heavy rain',
    13: 'Heavy snow',
    14: 'Severe thunderstorms with surface wind 62–87 km/h',
    15: 'Very severe thunderstorms with surface wind above 87 km/h',
    17: 'Hail',
    18: 'Severe dust storm',
    19: 'High probability of lightning',
}
_NOWCAST_SEVERITY = {2: 'Moderate', 3: 'Severe', 4: 'Extreme'}


@dataclass(frozen=True, slots=True)
class _FeedDocument:
    """One linked CAP document discovered in an upstream feed."""

    url: str
    route: str
    feed_reference_time: datetime | None
    rss_author: str | None = None


@dataclass(slots=True)
class _ParsedDocument:
    """CAP lifecycle metadata and its optional normalized alert."""

    alert: Alert | None
    identifier: str
    sender: str
    sent: datetime | None
    status: str
    message_type: str
    references: list[tuple[str, str, str]]
    route: str


@dataclass(frozen=True, slots=True)
class _SachetFeedItem:
    """Minimal SACHET RSS metadata used for safe pre-filtering."""

    url: str
    author: str | None


class IMDIndiaBackend(WarningBackend):
    """Union the IMD WMO mirror with verified IMD-origin SACHET CAP."""

    backend_id = 'imd_india'

    def __init__(self) -> None:
        """Create the cookie-aware ETag cache required by SACHET."""
        self._sachet_session = ETagCachingSession(max_entries=2048)

    def fetch_alerts(
        self,
        source: WarningSource,
        *,
        lat: float | None = None,
        lon: float | None = None,
        lang: str | None = None,
        debug: bool = False,
    ) -> list[Alert]:
        """Return current IMD warnings from official structured routes."""
        del lat, lon
        preferred_lang = lang or source.lang

        wmo_root = fetch_feed_root(source, debug=debug)
        wmo_documents = (
            [
                _FeedDocument(url=url, route='WMO Alert Hub mirror', feed_reference_time=_feed_time(wmo_root))
                for url in _imd_india_alert_urls(wmo_root, base_url=source.url)
            ]
            if wmo_root is not None and source.url
            else []
        )

        sachet_root = _fetch_sachet_feed(debug=debug)
        sachet_items = _sachet_feed_items(sachet_root) if sachet_root is not None else []
        sachet_reference_time = _feed_time(sachet_root) if sachet_root is not None else None
        sachet_documents = [
            _FeedDocument(
                url=item.url,
                route='NDMA SACHET relay',
                feed_reference_time=sachet_reference_time,
                rss_author=item.author,
            )
            for item in sachet_items
            if _rss_author_is_imd(item.author)
        ]

        work = [*wmo_documents, *sachet_documents]
        emit_progress('alerts_total', source=source.id, total=len(work), phase='documents')
        parsed_documents: list[_ParsedDocument] = []
        malformed = 0
        excluded = 0
        stale = 0
        polygon_fetch_enabled = True
        for completed, document in enumerate(work, start=1):
            try:
                payload = self._fetch_document(document, debug=debug)
                parsed = _parse_document(
                    payload,
                    source=source.id,
                    preferred_lang=preferred_lang,
                    url=document.url,
                    route=document.route,
                )
                if parsed is None:
                    malformed += 1
                    continue
                if (parsed.status and parsed.status != 'actual') or parsed.message_type not in {
                    'alert',
                    'update',
                    'cancel',
                }:
                    excluded += 1
                    continue
                if document.route == 'NDMA SACHET relay':
                    if not _is_imd_meteorological_document(payload, parsed):
                        excluded += 1
                        continue
                    if parsed.alert is not None:
                        _add_sachet_provenance(parsed.alert, parsed, rss_author=document.rss_author)
                        if polygon_fetch_enabled:
                            polygon_fetch_enabled = _enrich_sachet_geometry(
                                parsed.alert,
                                cap_identifier=parsed.identifier,
                                session=self._sachet_session,
                                debug=debug,
                            )
                elif parsed.alert is not None:
                    parsed.alert.parameters.setdefault('wevva:ingestion route', []).append(document.route)

                if (
                    parsed.alert is not None
                    and document.feed_reference_time is not None
                    and parsed.alert.expires is not None
                    and _as_utc(parsed.alert.expires) < document.feed_reference_time
                ):
                    stale += 1
                    continue
                parsed_documents.append(parsed)
            except BackendError:
                continue
            finally:
                emit_progress(
                    'alerts_checked',
                    source=source.id,
                    completed=completed,
                    total=len(work),
                    phase='documents',
                )

        alerts, duplicate_count = _apply_lifecycle_and_deduplicate(parsed_documents)
        nowcasts = _fetch_imd_nowcasts(source=source.id, debug=debug)
        alerts.extend(nowcasts)
        if debug:
            _log_diagnostics(
                source=source.id,
                wmo_items=len(wmo_documents),
                sachet_total=len(sachet_items),
                sachet_eligible=len(sachet_documents),
                parsed=len(parsed_documents),
                excluded=excluded,
                malformed=malformed,
                stale=stale,
                duplicates=duplicate_count,
                nowcasts=len(nowcasts),
                alerts=alerts,
            )
        return alerts

    def _fetch_document(self, document: _FeedDocument, *, debug: bool) -> str:
        if document.route == 'NDMA SACHET relay':
            return self._sachet_session.fetch_text(
                document.url,
                headers={'Accept': CAP_ACCEPT},
                debug=debug,
            )
        return fetch_text(document.url, headers={'Accept': CAP_ACCEPT}, debug=debug)


def _imd_india_alert_urls(root: ElementTree.Element, *, base_url: str) -> list[str]:
    """Return candidate CAP URLs from the dedicated IMD WMO RSS feed."""
    urls: list[str] = []
    for item in root.iter():
        if local_name(item.tag) != 'item':
            continue
        url = absolute_url(base_url, child_text(item, 'link'))
        if url and '/in-imd-en/' in url.lower() and url.lower().endswith('.xml'):
            urls.append(url)
    return list(dict.fromkeys(urls))


def _fetch_sachet_feed(*, debug: bool) -> ElementTree.Element | None:
    """Fetch the national SACHET RSS feed independently of the WMO route."""
    try:
        payload = fetch_text(
            SACHET_RSS_URL,
            headers={'Accept': 'application/rss+xml, application/xml, text/xml'},
            debug=debug,
        )
        return ElementTree.fromstring(payload)
    except (BackendError, ElementTree.ParseError):
        return None


def _sachet_feed_items(root: ElementTree.Element) -> list[_SachetFeedItem]:
    """Return unique, safely formed SACHET CAP links and their authors."""
    items: list[_SachetFeedItem] = []
    seen: set[str] = set()
    for item in root.iter():
        if local_name(item.tag) != 'item':
            continue
        url = child_text(item, 'link')
        if not url or not _validated_sachet_url(url, path=_SACHET_CAP_PATH):
            continue
        if url in seen:
            continue
        seen.add(url)
        items.append(_SachetFeedItem(url=url, author=child_text(item, 'author')))
    return items


def _rss_author_is_imd(author: str | None) -> bool:
    """Return whether RSS attribution explicitly names an IMD office."""
    if not author:
        return False
    organization = author.rsplit('(', maxsplit=1)[-1].rstrip(')').strip()
    return _is_imd_sender(organization)


def _parse_document(
    payload: str,
    *,
    source: str,
    preferred_lang: str | None,
    url: str,
    route: str,
) -> _ParsedDocument | None:
    """Parse CAP envelope metadata plus the shared normalized alert."""
    try:
        root = ElementTree.fromstring(payload)
    except ElementTree.ParseError:
        return None
    if local_name(root.tag) != 'alert':
        return None

    identifier = child_text(root, 'identifier') or ''
    message_type = (child_text(root, 'msgType') or '').strip().casefold()
    return _ParsedDocument(
        alert=parse_cap_alert(payload, source=source, preferred_lang=preferred_lang, url=url),
        identifier=identifier,
        sender=child_text(root, 'sender') or '',
        sent=WarningBackend.parse_datetime(child_text(root, 'sent')),
        status=(child_text(root, 'status') or '').strip().casefold(),
        message_type=message_type,
        references=_parse_references(child_text(root, 'references')),
        route=route,
    )


def _parse_references(value: str | None) -> list[tuple[str, str, str]]:
    """Parse CAP space-delimited ``sender,identifier,sent`` references."""
    references: list[tuple[str, str, str]] = []
    for entry in (value or '').split():
        parts = entry.rsplit(',', maxsplit=2)
        if len(parts) == 3 and all(part.strip() for part in parts):
            sender, identifier, sent = (part.strip() for part in parts)
            references.append((sender, identifier, sent))
    return references


def _is_imd_meteorological_document(payload: str, document: _ParsedDocument) -> bool:
    """Verify IMD authorship/provenance and CAP meteorological category."""
    if not (_is_imd_sender(document.sender) or any(_is_imd_sender(item[0]) for item in document.references)):
        return False
    try:
        root = ElementTree.fromstring(payload)
    except ElementTree.ParseError:
        return False
    categories = [
        (node.text or '').strip().casefold()
        for node in root.iter()
        if local_name(node.tag) == 'category'
    ]
    return 'met' in categories or (document.message_type == 'cancel' and not categories)


def _is_imd_sender(value: str) -> bool:
    return _IMD_SENDER_RE.match(value.strip()) is not None


def _add_sachet_provenance(
    alert: Alert,
    document: _ParsedDocument,
    *,
    rss_author: str | None,
) -> None:
    """Retain SACHET envelope and relay provenance on the normalized alert."""
    alert.parameters.setdefault('wevva:ingestion route', []).append(document.route)
    if document.sender:
        alert.parameters.setdefault('SACHET CAP sender', []).append(document.sender)
    if document.sent is not None:
        alert.parameters.setdefault('SACHET CAP sent', []).append(document.sent.isoformat())
    if rss_author:
        alert.parameters.setdefault('SACHET RSS author', []).append(rss_author)
    if document.references:
        values = alert.parameters.setdefault('SACHET CAP references', [])
        for reference in document.references:
            text = ','.join(reference)
            if text not in values:
                values.append(text)


def _enrich_sachet_geometry(
    alert: Alert,
    *,
    cap_identifier: str,
    session: ETagCachingSession,
    debug: bool,
) -> bool:
    """Use the official external polygon only when inline CAP geometry is absent."""
    if alert.geometry is not None:
        return True
    polygon_urls = alert.parameters.get('Polygon URL', [])
    for url in polygon_urls:
        expected_identifier = _validated_sachet_url(url, path=_SACHET_POLYGON_PATH)
        if expected_identifier is None or expected_identifier not in cap_identifier:
            continue
        try:
            payload = session.fetch_text(
                url,
                headers={'Accept': 'application/xml, text/xml'},
                debug=debug,
            )
        except BackendError as exc:
            if getattr(exc.__cause__, 'code', None) == 403 or '403' in str(exc):
                return False
            continue
        geometry = _parse_sachet_polygon_document(payload, expected_identifier=expected_identifier)
        if geometry is not None:
            alert.geometry = geometry
            return True
    return True


def _parse_sachet_polygon_document(
    payload: str,
    *,
    expected_identifier: str,
) -> dict[str, object] | None:
    """Parse SACHET's small ``alert/identifier/polygon`` companion XML."""
    try:
        root = ElementTree.fromstring(payload)
    except ElementTree.ParseError:
        return None
    identifier = child_text(root, 'identifier') or ''
    if expected_identifier not in identifier:
        return None

    rings: list[list[list[float]]] = []
    seen: set[tuple[tuple[float, float], ...]] = set()
    for node in root.iter():
        if local_name(node.tag) != 'polygon':
            continue
        ring = _parse_cap_polygon((node.text or '').strip())
        if not ring:
            continue
        key = tuple((point[0], point[1]) for point in ring)
        if key in seen:
            continue
        seen.add(key)
        rings.append(ring)
    return _rings_to_geometry(rings)


def _validated_sachet_url(url: str, *, path: str) -> str | None:
    """Return the numeric SACHET identifier for one exact official URL."""
    parsed = urlparse(url.strip())
    try:
        port = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme != 'https'
        or parsed.hostname != _SACHET_HOST
        or port is not None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path != path
        or parsed.fragment
    ):
        return None
    query = parse_qs(parsed.query, keep_blank_values=True)
    if set(query) != {'identifier'} or len(query['identifier']) != 1:
        return None
    identifier = query['identifier'][0]
    return identifier if identifier.isdigit() else None


def _feed_time(root: ElementTree.Element) -> datetime | None:
    """Return the newest channel/item RSS time normalized to UTC."""
    channel = next((node for node in root.iter() if local_name(node.tag) == 'channel'), None)
    if channel is None:
        return None
    values = [child_text(channel, 'pubDate'), child_text(channel, 'lastBuildDate')]
    values.extend(
        child_text(item, 'pubDate')
        for item in root.iter()
        if local_name(item.tag) == 'item'
    )
    times = [parsed for value in values if value and (parsed := _parse_feed_time(value)) is not None]
    return max(times, default=None)


def _fetch_imd_nowcasts(*, source: str, debug: bool) -> list[Alert]:
    """Fetch current warning-coloured district nowcasts from IMD's WFS."""
    try:
        payload = fetch_json(
            IMD_NOWCAST_WFS_URL,
            params={
                'service': 'WFS',
                'version': '2.0.0',
                'request': 'GetFeature',
                'typeNames': 'imd:NowcastWarningDistrict',
                'outputFormat': 'application/json',
                'srsName': 'EPSG:4326',
                'CQL_FILTER': 'Color > 1',
                'sortBy': 'Obj_id',
                'count': 1000,
            },
            headers={'Accept': 'application/geo+json, application/json'},
            debug=debug,
        )
    except BackendError:
        return []
    if not isinstance(payload, dict) or not isinstance(payload.get('features'), list):
        return []

    alerts: list[Alert] = []
    for feature in payload['features']:
        alert = _parse_imd_nowcast(feature, source=source)
        if alert is not None:
            alerts.append(alert)
    return alerts


def _parse_imd_nowcast(feature: object, *, source: str) -> Alert | None:
    """Normalize one official IMD district-nowcast GeoJSON feature."""
    if not isinstance(feature, dict):
        return None
    properties = feature.get('properties')
    geometry = feature.get('geometry')
    if not isinstance(properties, dict) or not _is_polygon_geometry(geometry):
        return None

    color = _integer(properties.get('Color'))
    severity = _NOWCAST_SEVERITY.get(color)
    district = _text(properties.get('District')) or _text(properties.get('State_District'))
    state = _text(properties.get('State'))
    object_id = _scalar_text(properties.get('Obj_id')) or _scalar_text(properties.get('id'))
    onset, expires = _nowcast_validity(
        properties.get('Date'),
        properties.get('toi'),
        properties.get('vupto'),
    )
    if severity is None or district is None or object_id is None or onset is None or expires is None:
        return None

    categories, raw_categories = _nowcast_categories(properties)
    event = '; '.join(categories) or 'District nowcast'
    publisher_message = _text(properties.get('message'))
    headline = publisher_message or f'{event} for {district}'
    color_name = {2: 'Yellow', 3: 'Orange', 4: 'Red'}[color]
    parameters = {
        'wevva:ingestion route': ['IMD public WFS district nowcast'],
        'IMD warning colour': [f'{color_name} ({color})'],
        'IMD nowcast category': raw_categories,
        'IMD warning date': [onset.date().isoformat()],
        'IMD time of issue': [onset.strftime('%H%M')],
        'IMD valid up to': [expires.strftime('%H%M')],
    }
    if publisher_message is None:
        parameters['wevva:normalization'] = [
            'headline generated from structured IMD nowcast categories and district',
        ]
    for source_key, output_key in (
        ('MC_RMC', 'IMD issuing centre'),
        ('update_time', 'IMD update time'),
        ('Data', 'IMD source data'),
    ):
        value = _text(properties.get(source_key))
        if value is not None:
            parameters[output_key] = [value]

    area_names = [district]
    if state and state.casefold() != district.casefold():
        area_names.append(state)
    return Alert(
        id=f'imd-nowcast:{onset.date().isoformat()}:{object_id}:{onset:%H%M}:{expires:%H%M}',
        source=source,
        event=event,
        headline=headline,
        url=IMD_NOWCAST_MAP_URL,
        severity=severity,
        description=_text(properties.get('impact')),
        instruction=_text(properties.get('action')),
        onset=onset,
        expires=expires,
        area_names=area_names,
        geocodes={'IMD Obj_id': [object_id]},
        parameters=parameters,
        geometry=geometry,
    )


def _nowcast_categories(properties: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Return human-readable and raw active category values."""
    labels: list[str] = []
    raw: list[str] = []
    for number in range(2, 20):
        key = f'cat{number}'
        value = properties.get(key)
        if number == 16:
            text = _text(value)
            if text is None or text == '0':
                continue
            label = text if text != '16' else 'Other warning'
        elif _integer(value) in {None, 0}:
            continue
        else:
            label = _NOWCAST_CATEGORIES.get(number)
            if label is None:
                continue
        labels.append(label)
        raw.append(f'{key}={value}')
    return list(dict.fromkeys(labels)), raw


def _nowcast_validity(
    date_value: object,
    onset_value: object,
    expiry_value: object,
) -> tuple[datetime | None, datetime | None]:
    """Parse IMD's local-date and HHMM validity fields as India time."""
    date_text = _text(date_value)
    onset_text = _hhmm(onset_value)
    expiry_text = _hhmm(expiry_value)
    if date_text is None or onset_text is None or expiry_text is None:
        return None, None
    try:
        date = datetime.strptime(date_text[:10], '%Y-%m-%d').date()
        onset = datetime.combine(date, onset_text, tzinfo=_INDIA_TIME)
        expires = datetime.combine(date, expiry_text, tzinfo=_INDIA_TIME)
    except ValueError:
        return None, None
    if expires <= onset:
        expires += timedelta(days=1)
    return onset, expires


def _hhmm(value: object) -> time | None:
    text = _text(value)
    if text is None:
        return None
    digits = text.replace(':', '').zfill(4)
    if not digits.isdigit() or len(digits) != 4:
        return None
    try:
        return datetime.strptime(digits, '%H%M').time()
    except ValueError:
        return None


def _integer(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _scalar_text(value: object) -> str | None:
    if isinstance(value, (int, float)):
        return str(value)
    return _text(value)


def _is_polygon_geometry(value: object) -> bool:
    return (
        isinstance(value, dict)
        and value.get('type') in {'Polygon', 'MultiPolygon'}
        and isinstance(value.get('coordinates'), list)
        and bool(value['coordinates'])
    )


def _parse_feed_time(value: str) -> datetime | None:
    """Parse one RFC 2822 or ISO feed timestamp."""
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        parsed = WarningBackend.parse_datetime(value)
    return _as_utc(parsed) if parsed is not None else None


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _apply_lifecycle_and_deduplicate(
    documents: list[_ParsedDocument],
) -> tuple[list[Alert], int]:
    """Apply CAP cancellation/update references and cross-route deduplication."""
    cancelled = {
        identifier
        for document in documents
        if document.message_type == 'cancel'
        for _, identifier, _ in document.references
    }
    ordered = sorted(
        documents,
        key=lambda item: _as_utc(item.sent).timestamp() if item.sent is not None else float('-inf'),
        reverse=True,
    )

    alerts: list[Alert] = []
    claimed_identifiers: set[str] = set()
    semantic_keys: set[tuple[object, ...]] = set()
    duplicates = 0
    for document in ordered:
        if document.alert is None or document.message_type == 'cancel':
            continue
        identities = {document.identifier, *(item[1] for item in document.references)} - {''}
        if identities & cancelled or identities & claimed_identifiers:
            duplicates += 1
            continue

        semantic_key = _semantic_key(document.alert)
        if semantic_key in semantic_keys:
            duplicates += 1
            claimed_identifiers.update(identities)
            continue

        alerts.append(document.alert)
        claimed_identifiers.update(identities)
        semantic_keys.add(semantic_key)
    return alerts, duplicates


def _semantic_key(alert: Alert) -> tuple[object, ...]:
    def normalized(value: str | None) -> str:
        return ' '.join((value or '').casefold().split())

    geocodes = tuple(
        sorted(
            (key.casefold(), tuple(sorted(normalized(value) for value in values)))
            for key, values in alert.geocodes.items()
        )
    )
    return (
        normalized(alert.headline),
        normalized(alert.event),
        normalized(alert.severity),
        normalized(alert.urgency),
        normalized(alert.certainty),
        _as_utc(alert.onset).isoformat() if alert.onset else None,
        _as_utc(alert.expires).isoformat() if alert.expires else None,
        normalized(alert.description),
        normalized(alert.instruction),
        tuple(sorted(normalized(value) for value in alert.area_names)),
        geocodes,
    )


def _log_diagnostics(
    *,
    source: str,
    wmo_items: int,
    sachet_total: int,
    sachet_eligible: int,
    parsed: int,
    excluded: int,
    malformed: int,
    stale: int,
    duplicates: int,
    nowcasts: int,
    alerts: list[Alert],
) -> None:
    """Emit a compact India source audit through the existing debug channel."""
    active_times = [_as_utc(value) for alert in alerts for value in (alert.onset, alert.expires) if value]
    logging.info(
        'Provider %r audit: WMO items=%s; SACHET total=%s; SACHET IMD-eligible=%s; '
        'parsed=%s; excluded=%s; malformed=%s; stale=%s; duplicates=%s; WFS nowcasts=%s; alerts=%s; '
        'geometry=%s; headline=%s; description=%s; instruction=%s; oldest=%s; newest=%s.',
        source,
        wmo_items,
        sachet_total,
        sachet_eligible,
        parsed,
        excluded,
        malformed,
        stale,
        duplicates,
        nowcasts,
        len(alerts),
        sum(alert.geometry is not None for alert in alerts),
        sum(bool(alert.headline) for alert in alerts),
        sum(bool(alert.description) for alert in alerts),
        sum(bool(alert.instruction) for alert in alerts),
        min(active_times).isoformat() if active_times else None,
        max(active_times).isoformat() if active_times else None,
    )
