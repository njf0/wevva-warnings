"""Provider backend for Met Eireann CAP feeds."""

from __future__ import annotations

from xml.etree import ElementTree

from ..models import Alert
from ..sources import WarningSource
from ._cap_feed import absolute_url, child_text, fetch_cap_documents, fetch_feed_root, local_name
from .base import WarningBackend


class MetEireannBackend(WarningBackend):
    """Fetch alerts from Met Eireann CAP feeds."""

    backend_id = 'met_eireann'

    def fetch_alerts(
        self,
        source: WarningSource,
        *,
        lat: float | None = None,
        lon: float | None = None,
        lang: str | None = None,
        debug: bool = False,
    ) -> list[Alert]:
        """Fetch alerts for a Met Eireann CAP source."""
        del lat, lon
        root = fetch_feed_root(source, debug=debug)
        if root is None or not source.url:
            return []
        return fetch_cap_documents(
            source,
            _met_eireann_alert_urls(root, base_url=source.url),
            preferred_lang=lang or source.lang,
            debug=debug,
        )


def _met_eireann_alert_urls(root: ElementTree.Element, *, base_url: str) -> list[str]:
    """Return candidate CAP URLs from a Met Eireann RSS feed."""
    urls: list[str] = []
    for item in root.iter():
        if local_name(item.tag) != 'item':
            continue
        url = absolute_url(base_url, child_text(item, 'link'))
        if url and 'cap.met.ie' in url.lower() and url.lower().endswith('.xml'):
            urls.append(url)
    return list(dict.fromkeys(urls))
