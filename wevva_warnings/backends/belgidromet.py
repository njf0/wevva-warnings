"""Provider backend for Belgidromet CAP Atom feeds."""

from __future__ import annotations

from xml.etree import ElementTree

from ..models import Alert
from ..sources import WarningSource
from ._cap_feed import absolute_url, fetch_cap_documents, fetch_feed_root, local_name
from .base import WarningBackend


class BelgidrometBackend(WarningBackend):
    """Fetch alerts from Belgidromet CAP feeds."""

    backend_id = 'belgidromet'

    def fetch_alerts(
        self,
        source: WarningSource,
        *,
        lat: float | None = None,
        lon: float | None = None,
        lang: str | None = None,
        debug: bool = False,
    ) -> list[Alert]:
        """Fetch alerts for a Belgidromet CAP source."""
        del lat, lon
        root = fetch_feed_root(source, debug=debug)
        if root is None or not source.url:
            return []
        return fetch_cap_documents(
            source,
            _belgidromet_alert_urls(root, base_url=source.url),
            preferred_lang=lang or source.lang,
            debug=debug,
        )


def _belgidromet_alert_urls(root: ElementTree.Element, *, base_url: str) -> list[str]:
    """Return candidate CAP URLs from a Belgidromet Atom feed."""
    urls: list[str] = []
    for entry in root.iter():
        if local_name(entry.tag) != 'entry':
            continue

        related_urls: list[str] = []
        alternate_urls: list[str] = []
        for child in entry:
            if local_name(child.tag) != 'link':
                continue
            href = absolute_url(base_url, child.get('href'))
            if not href or not href.lower().endswith('.xml'):
                continue
            rel = (child.get('rel') or '').lower()
            if rel == 'related':
                related_urls.append(href)
            elif rel == 'alternate':
                alternate_urls.append(href)

        urls.extend(related_urls or alternate_urls)

    return list(dict.fromkeys(urls))
