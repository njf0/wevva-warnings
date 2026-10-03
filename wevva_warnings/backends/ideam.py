"""Colombia IDEAM CAP backend."""

from __future__ import annotations

from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin
from xml.etree import ElementTree

from ..models import Alert
from ..sources import WarningSource
from ._cap_feed import child_text, fetch_cap_documents, fetch_feed_root, local_name
from .base import WarningBackend


_IDEAM_MIRROR_PREFIX = 'https://severeweather.wmo.int/v2/cap-alerts/co-ideam-es/'


class IDEAMBackend(WarningBackend):
    """Fetch current IDEAM alerts from the WMO SWIC CAP mirror."""

    backend_id = 'ideam'

    def fetch_alerts(
        self,
        source: WarningSource,
        *,
        lat: float | None = None,
        lon: float | None = None,
        lang: str | None = None,
        debug: bool = False,
    ) -> list[Alert]:
        """Return the current polygonal IDEAM CAP alerts."""
        del lat, lon
        root = fetch_feed_root(source, debug=debug)
        if root is None or not source.url:
            return []
        alert_urls = _current_ideam_alert_urls(root, base_url=source.url)
        return fetch_cap_documents(
            source,
            alert_urls,
            preferred_lang=lang or source.lang,
            debug=debug,
        )


def _current_ideam_alert_urls(root: ElementTree.Element, *, base_url: str) -> list[str]:
    """Return unique IDEAM mirror documents current at feed publication time."""
    channel = next((node for node in root.iter() if local_name(node.tag) == 'channel'), None)
    reference_time = _parse_datetime(child_text(channel, 'pubDate')) if channel is not None else None
    if reference_time is None:
        return []

    urls: list[str] = []
    for item in root.iter():
        if local_name(item.tag) != 'item':
            continue
        status = (child_text(item, 'status') or '').strip().casefold()
        if status and status != 'actual':
            continue
        if (child_text(item, 'msgType') or '').strip().casefold() == 'cancel':
            continue
        expires = _parse_datetime(child_text(item, 'expires'))
        if expires is not None and expires < reference_time:
            continue

        link = child_text(item, 'link')
        if not link:
            continue
        url = urljoin(base_url, link.strip())
        if not url.startswith(_IDEAM_MIRROR_PREFIX) or not url.lower().endswith('.xml'):
            continue
        urls.append(url)
    return list(dict.fromkeys(urls))


def _parse_datetime(value: str | None) -> datetime | None:
    """Parse one feed timestamp and normalize it to UTC."""
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value.strip())
    except (TypeError, ValueError):
        parsed = WarningBackend.parse_datetime(value.strip())
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
