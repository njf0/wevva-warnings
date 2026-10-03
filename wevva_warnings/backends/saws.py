"""South African Weather Service CAP backend."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
import logging
from urllib.parse import urljoin
from xml.etree import ElementTree

from .._debug import emit_progress
from ..cap import parse_cap_alert
from ..models import Alert
from ..sources import WarningSource
from ._cap_feed import CAP_ACCEPT, child_text, fetch_feed_root, local_name
from .base import BackendError, WarningBackend, fetch_text


_SAWS_MIRROR_PREFIX = 'https://severeweather.wmo.int/v2/cap-alerts/za-saws-en/'


class SAWSBackend(WarningBackend):
    """Fetch current SAWS warnings from the WMO SWIC CAP mirror."""

    backend_id = 'saws'

    def fetch_alerts(
        self,
        source: WarningSource,
        *,
        lat: float | None = None,
        lon: float | None = None,
        lang: str | None = None,
        debug: bool = False,
    ) -> list[Alert]:
        """Return current polygonal SAWS CAP warnings."""
        del lat, lon
        root = fetch_feed_root(source, debug=debug)
        if root is None or not source.url:
            return []

        alert_urls = _current_saws_alert_urls(root, base_url=source.url)
        if debug:
            logging.info('Provider %r found %s current CAP documents.', source.id, len(alert_urls))
        emit_progress('alerts_total', source=source.id, total=len(alert_urls), phase='documents')

        alerts: list[Alert] = []
        seen: set[tuple[str, str]] = set()
        for completed, alert_url in enumerate(alert_urls, start=1):
            try:
                payload = fetch_text(
                    alert_url,
                    headers={'Accept': CAP_ACCEPT},
                    debug=debug,
                )
                for alert in _parse_saws_alerts(
                    payload,
                    source=source.id,
                    preferred_lang=lang or source.lang,
                    url=alert_url,
                ):
                    key = (alert.source, alert.id)
                    if key in seen:
                        continue
                    seen.add(key)
                    alerts.append(alert)
            except BackendError:
                continue
            finally:
                emit_progress(
                    'alerts_checked',
                    source=source.id,
                    completed=completed,
                    total=len(alert_urls),
                    phase='documents',
                )
        return alerts


def _current_saws_alert_urls(root: ElementTree.Element, *, base_url: str) -> list[str]:
    """Return non-expired, unique SAWS CAP URLs from the SWIC history feed."""
    items = [element for element in root.iter() if local_name(element.tag) == 'item']
    reference_time = _feed_reference_time(root, items)
    if reference_time is None:
        return []

    urls: list[str] = []
    for item in items:
        status = (child_text(item, 'status') or '').strip().casefold()
        if status and status != 'actual':
            continue
        message_type = (child_text(item, 'msgType') or '').strip().casefold()
        if message_type == 'cancel':
            continue

        expires = _parse_feed_datetime(child_text(item, 'expires'))
        if expires is not None and expires < reference_time:
            continue

        link = child_text(item, 'link')
        if not link:
            continue
        url = urljoin(base_url, link.strip())
        if not url.startswith(_SAWS_MIRROR_PREFIX) or not url.lower().endswith('.xml'):
            continue
        urls.append(url)
    return list(dict.fromkeys(urls))


def _feed_reference_time(
    root: ElementTree.Element,
    items: list[ElementTree.Element],
) -> datetime | None:
    """Return the feed build time, falling back to the newest item timestamp."""
    channel = next((element for element in root.iter() if local_name(element.tag) == 'channel'), None)
    if channel is not None:
        reference = _parse_feed_datetime(child_text(channel, 'pubDate'))
        if reference is not None:
            return reference

    item_times = [
        parsed
        for item in items
        if (parsed := _parse_feed_datetime(child_text(item, 'pubDate'))) is not None
    ]
    return max(item_times, default=None)


def _parse_feed_datetime(value: str | None) -> datetime | None:
    """Parse an RFC 2822 or ISO timestamp and normalize it to UTC."""
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        parsed = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        parsed = WarningBackend.parse_datetime(text)
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _parse_saws_alerts(
    payload: str | bytes,
    *,
    source: str,
    preferred_lang: str | None,
    url: str,
) -> list[Alert]:
    """Parse every matching-language SAWS info block as a distinct alert."""
    try:
        root = ElementTree.fromstring(payload)
    except ElementTree.ParseError:
        return []
    if local_name(root.tag) != 'alert':
        return []

    status = (child_text(root, 'status') or '').strip().casefold()
    if status and status != 'actual':
        return []
    if (child_text(root, 'msgType') or '').strip().casefold() == 'cancel':
        return []

    infos = [child for child in root if local_name(child.tag) == 'info']
    selected_indices = _selected_info_indices(infos, preferred_lang=preferred_lang)
    provider_identifier = child_text(root, 'identifier')
    alerts: list[Alert] = []
    for info_index in selected_indices:
        alert_root = deepcopy(root)
        cloned_infos = [child for child in alert_root if local_name(child.tag) == 'info']
        for index, info in reversed(list(enumerate(cloned_infos))):
            if index != info_index:
                alert_root.remove(info)

        alert = parse_cap_alert(
            ElementTree.tostring(alert_root, encoding='unicode'),
            source=source,
            preferred_lang=preferred_lang,
            url=url,
        )
        if alert is None:
            continue
        if len(selected_indices) > 1:
            raw_identifier = provider_identifier or alert.id
            alert.id = f'{raw_identifier}#info-{info_index + 1}'
            alert.parameters.setdefault('CAP identifier', []).append(raw_identifier)
            alert.parameters.setdefault('CAP info block', []).append(str(info_index + 1))
        alerts.append(alert)
    return alerts


def _selected_info_indices(
    infos: list[ElementTree.Element],
    *,
    preferred_lang: str | None,
) -> list[int]:
    """Return all info-block indices for the preferred language fallback."""
    if not infos:
        return []
    preferred = _normalize_language(preferred_lang)
    if preferred:
        matches = [
            index
            for index, info in enumerate(infos)
            if _normalize_language(child_text(info, 'language')) == preferred
        ]
        if matches:
            return matches
    english = [
        index
        for index, info in enumerate(infos)
        if _normalize_language(child_text(info, 'language')) == 'en'
    ]
    return english or [0]


def _normalize_language(value: str | None) -> str:
    """Return the lowercase base language from one source or CAP language."""
    text = (value or '').split(',', 1)[0].strip().lower()
    return text.split('-', 1)[0].split('_', 1)[0]
