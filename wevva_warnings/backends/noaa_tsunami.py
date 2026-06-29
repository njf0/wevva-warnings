"""Provider backend for NOAA tsunami CAP feeds."""

from __future__ import annotations

from xml.etree import ElementTree

from ..cap import parse_cap_alert
from ..models import Alert
from ..sources import WarningSource
from ._cap_feed import absolute_url, fetch_cap_documents, local_name
from .base import BackendError, WarningBackend, fetch_text


class NOAATsunamiBackend(WarningBackend):
    """Fetch tsunami alerts from NOAA tsunami Atom/CAP endpoints."""

    backend_id = 'noaa_tsunami'

    def fetch_alerts(
        self,
        source: WarningSource,
        *,
        lat: float | None = None,
        lon: float | None = None,
        lang: str | None = None,
        debug: bool = False,
    ) -> list[Alert]:
        """Fetch alerts for a NOAA tsunami source."""
        del lat, lon
        if not source.url:
            return []

        preferred_lang = lang or source.lang
        try:
            payload = fetch_text(
                source.url,
                headers={'Accept': 'application/cap+xml, application/atom+xml, application/rss+xml, application/xml, text/xml'},
                debug=debug,
            )
        except BackendError:
            return []
        try:
            root = ElementTree.fromstring(payload)
        except ElementTree.ParseError:
            return []

        if local_name(root.tag) == 'alert':
            alert = parse_cap_alert(payload, source=source.id, preferred_lang=preferred_lang, url=source.url)
            return [alert] if alert is not None else []

        return fetch_cap_documents(
            source,
            _noaa_tsunami_alert_urls(root, base_url=source.url),
            preferred_lang=preferred_lang,
            debug=debug,
        )


def _noaa_tsunami_alert_urls(root: ElementTree.Element, *, base_url: str) -> list[str]:
    """Return CAP document URLs from a NOAA tsunami feed."""
    urls: list[str] = []
    for entry in root.iter():
        if local_name(entry.tag) not in {'entry', 'item'}:
            continue
        for element in entry.iter():
            href = element.attrib.get('href') or element.attrib.get('src')
            rel = (element.attrib.get('rel') or '').lower()
            link_type = (element.attrib.get('type') or '').lower()
            if not href:
                continue
            url = absolute_url(base_url, href)
            if not url:
                continue
            lowered = url.lower()
            if 'application/cap+xml' in link_type or rel == 'related' or lowered.endswith('cap.xml'):
                urls.append(url)
    return list(dict.fromkeys(urls))
