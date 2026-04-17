"""Provider backend for MetService New Zealand CAP feeds."""

from __future__ import annotations

from xml.etree import ElementTree

from ..models import Alert
from ..sources import WarningSource
from ._cap_feed import absolute_url, child_text, fetch_cap_documents, fetch_feed_root, local_name
from .base import WarningBackend


class MetServiceNZBackend(WarningBackend):
    """Fetch alerts from MetService New Zealand CAP feeds."""

    backend_id = 'metservice_nz'

    def fetch_alerts(
        self,
        source: WarningSource,
        *,
        lat: float | None = None,
        lon: float | None = None,
        lang: str | None = None,
        debug: bool = False,
    ) -> list[Alert]:
        """Fetch alerts for a MetService New Zealand CAP source.

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
            Alerts parsed from linked MetService CAP documents.

        """
        del lat, lon
        root = fetch_feed_root(source, debug=debug)
        if root is None or not source.url:
            return []
        return fetch_cap_documents(
            source,
            _metservice_nz_alert_urls(root, base_url=source.url),
            preferred_lang=lang or source.lang,
            debug=debug,
        )


def _metservice_nz_alert_urls(root: ElementTree.Element, *, base_url: str) -> list[str]:
    """Return candidate CAP URLs from a MetService RSS feed.

    Parameters
    ----------
    root : ElementTree.Element
        Root XML element of the MetService RSS feed.
    base_url : str
        Base URL used to resolve relative links.

    Returns
    -------
    list[str]
        Linked CAP document URLs discovered in the feed.

    """
    urls: list[str] = []
    for item in root.iter():
        if local_name(item.tag) != 'item':
            continue
        url = absolute_url(base_url, child_text(item, 'link'))
        if url and '/cap/alert?' in url.lower() and 'id=' in url.lower():
            urls.append(url)
    return list(dict.fromkeys(urls))
