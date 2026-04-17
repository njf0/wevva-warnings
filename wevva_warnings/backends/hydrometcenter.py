"""Provider backend for Hydrometcenter of Russia CAP Atom feeds."""

from __future__ import annotations

from xml.etree import ElementTree

from ..models import Alert
from ..sources import WarningSource
from ._cap_feed import absolute_url, fetch_cap_documents, fetch_feed_root, local_name
from .base import WarningBackend


class HydrometcenterBackend(WarningBackend):
    """Fetch alerts from Hydrometcenter of Russia CAP feeds."""

    backend_id = 'hydrometcenter'

    def fetch_alerts(
        self,
        source: WarningSource,
        *,
        lat: float | None = None,
        lon: float | None = None,
        lang: str | None = None,
        debug: bool = False,
    ) -> list[Alert]:
        """Fetch alerts for a Hydrometcenter CAP source.

        Parameters
        ----------
        source : WarningSource
            Source definition to query.
        lat : float | None, optional
            Unused for this backend. Included for interface compatibility.
        lon : float | None, optional
            Unused for this backend. Included for interface compatibility.
        lang : str | None, optional
            Preferred language code used when selecting CAP ``info`` blocks.
        debug : bool, optional
            If True, emit progress information while fetching alerts.

        Returns
        -------
        list[Alert]
            Alerts parsed from linked Hydrometcenter CAP documents.

        """
        del lat, lon
        root = fetch_feed_root(source, debug=debug)
        if root is None or not source.url:
            return []
        return fetch_cap_documents(
            source,
            _hydrometcenter_alert_urls(root, base_url=source.url),
            preferred_lang=lang or source.lang,
            debug=debug,
        )


def _hydrometcenter_alert_urls(root: ElementTree.Element, *, base_url: str) -> list[str]:
    """Return candidate CAP URLs from a Hydrometcenter Atom feed.

    Parameters
    ----------
    root : ElementTree.Element
        Root XML element of the Hydrometcenter Atom feed.
    base_url : str
        Base URL used to resolve relative links.

    Returns
    -------
    list[str]
        Linked CAP document URLs discovered in the feed.

    """
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
