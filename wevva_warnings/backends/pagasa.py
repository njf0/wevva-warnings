"""Provider backend for PAGASA Atom feeds."""

from __future__ import annotations

from urllib.parse import urljoin
from xml.etree import ElementTree

from ..models import Alert
from ..sources import WarningSource
from ._cap_feed import fetch_cap_documents, fetch_feed_root, local_name
from .base import WarningBackend


class PAGASABackend(WarningBackend):
    """Fetch alerts from PAGASA Atom feeds."""

    backend_id = 'pagasa'

    def fetch_alerts(
        self,
        source: WarningSource,
        *,
        lat: float | None = None,
        lon: float | None = None,
        lang: str | None = None,
        debug: bool = False,
    ) -> list[Alert]:
        """Fetch alerts for a PAGASA source."""
        del lat, lon
        root = fetch_feed_root(source, debug=debug)
        if root is None or not source.url:
            return []
        return fetch_cap_documents(
            source,
            _pagasa_alert_urls(root, base_url=source.url),
            preferred_lang=lang or source.lang,
            debug=debug,
        )


def _pagasa_alert_urls(root: ElementTree.Element, *, base_url: str) -> list[str]:
    """Return candidate CAP URLs from a PAGASA Atom feed."""
    urls: list[str] = []
    for entry in root.iter():
        if local_name(entry.tag) != 'entry':
            continue
        for child in entry:
            if local_name(child.tag) != 'link':
                continue
            href = (child.get('href') or '').strip()
            if not href:
                continue
            url = urljoin(base_url, href)
            if url.lower().endswith('.xml'):
                urls.append(url)
    return list(dict.fromkeys(urls))
