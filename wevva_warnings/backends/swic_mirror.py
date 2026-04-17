"""Provider backend for SWIC CAP mirror feeds."""

from __future__ import annotations

from xml.etree import ElementTree

from ..models import Alert
from ..sources import WarningSource
from ._cap_feed import absolute_url, child_text, fetch_cap_documents, fetch_feed_root, local_name
from .base import WarningBackend


class SWICMirrorBackend(WarningBackend):
    """Fetch alerts from severeweather.wmo.int SWIC mirror feeds."""

    backend_id = 'swic_mirror'

    def fetch_alerts(
        self,
        source: WarningSource,
        *,
        lat: float | None = None,
        lon: float | None = None,
        lang: str | None = None,
        debug: bool = False,
    ) -> list[Alert]:
        """Fetch alerts for a SWIC mirror source."""
        del lat, lon
        root = fetch_feed_root(source, debug=debug)
        if root is None or not source.url:
            return []
        return fetch_cap_documents(
            source,
            _swic_mirror_alert_urls(root, base_url=source.url),
            preferred_lang=lang or source.lang,
            debug=debug,
        )


def _swic_mirror_alert_urls(root: ElementTree.Element, *, base_url: str) -> list[str]:
    """Return candidate CAP URLs from a SWIC mirror RSS feed."""
    urls: list[str] = []
    for item in root.iter():
        if local_name(item.tag) != 'item':
            continue
        url = absolute_url(base_url, child_text(item, 'link'))
        if url and url.lower().endswith('.xml') and '/v2/cap-alerts/' in url.lower():
            urls.append(url)
    return list(dict.fromkeys(urls))
