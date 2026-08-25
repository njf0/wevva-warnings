"""Provider backend for PAGASA's current tropical-cyclone bulletin."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
import re

from ..models import Alert, TropicalProduct, TropicalSystem
from ..sources import WarningSource
from ._tropical_text import plain_text_to_markdown
from .base import BackendError, WarningBackend, fetch_text

_PHILIPPINE_TIME = timezone(timedelta(hours=8))
_NO_ACTIVE_RE = re.compile(r'no\s+active\s+tropical\s+cyclone', re.IGNORECASE)
_SYSTEM_RE = re.compile(
    r'\b(?P<classification>Super Typhoon|Typhoon|Severe Tropical Storm|Tropical Storm|Tropical Depression)'
    r'\s+[“"]?(?P<name>[A-Za-z][A-Za-z0-9-]*)[”"]?',
    re.IGNORECASE,
)
_ISSUED_RE = re.compile(
    r'issued\s+at\s+(?P<time>\d{1,2}:\d{2}\s*[AP]\.?M\.?)\s*,?\s*'
    r'(?P<date>\d{1,2}\s+[A-Za-z]+\s+\d{4})',
    re.IGNORECASE,
)
_BULLETIN_RE = re.compile(r'tropical\s+cyclone\s+bulletin\s+(?:nr\.?|no\.?|#)\s*(?P<number>[A-Za-z0-9-]+)', re.IGNORECASE)
_COORDINATE_RE = re.compile(
    r'\(\s*(?P<lat>\d+(?:\.\d+)?)\s*°?\s*(?P<lat_hemisphere>[NS])\s*,\s*'
    r'(?P<lon>\d+(?:\.\d+)?)\s*°?\s*(?P<lon_hemisphere>[EW])\s*\)',
    re.IGNORECASE,
)
_WIND_RE = re.compile(
    r'maximum\s+sustained\s+winds?\s+of\s+(?P<wind>\d+(?:\.\d+)?\s*km/h)'
    r'.{0,160}?(?:gustiness\s+(?:of\s+)?up\s+to|gusting\s+to)\s+(?P<gust>\d+(?:\.\d+)?\s*km/h)',
    re.IGNORECASE | re.DOTALL,
)
_WIND_WITHOUT_GUST_RE = re.compile(
    r'maximum\s+sustained\s+winds?\s+of\s+(?P<wind>\d+(?:\.\d+)?\s*km/h)',
    re.IGNORECASE,
)
_PRESSURE_RE = re.compile(r'central\s+pressure\s+of\s+(?P<pressure>\d+(?:\.\d+)?\s*hPa)', re.IGNORECASE)
_MOVEMENT_RE = re.compile(r'present\s+movement\s*\n+\s*(?P<movement>[^\n]+)', re.IGNORECASE)
_EXTENT_RE = re.compile(r'extent\s+of\s+tropical\s+cyclone\s+winds\s*\n+\s*(?P<extent>[^\n]+)', re.IGNORECASE)
_BLOCK_TAGS = {'br', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'p', 'section', 'td', 'th', 'tr'}


class PAGASATropicalBackend(WarningBackend):
    """Fetch PAGASA's current Philippine-area tropical system, if present."""

    backend_id = 'pagasa_tropical'

    def fetch_alerts(
        self,
        source: WarningSource,
        *,
        lat: float | None = None,
        lon: float | None = None,
        lang: str | None = None,
        debug: bool = False,
    ) -> list[Alert]:
        """Return no ordinary alerts for this tropical-system source."""
        del source, lat, lon, lang, debug
        return []

    def fetch_tropical_systems(
        self,
        source: WarningSource,
        *,
        lat: float | None = None,
        lon: float | None = None,
        lang: str | None = None,
        debug: bool = False,
    ) -> list[TropicalSystem]:
        """Fetch the current PAGASA tropical-cyclone bulletin.

        PAGASA serves the active bulletin as an ordinary public web page and
        replaces it with an explicit no-active-system message between events.
        The archive links on an inactive page are deliberately not treated as
        current systems.
        """
        del lat, lon, lang
        if not source.url:
            return []
        try:
            payload = fetch_text(source.url, headers={'Accept': 'text/html'}, debug=debug)
        except BackendError:
            return []

        system = _parse_pagasa_tropical_bulletin(payload, source=source.id, url=source.url)
        return [system] if system is not None else []

    def fetch_tropical_products(
        self,
        source: WarningSource,
        system: TropicalSystem,
        *,
        debug: bool = False,
    ) -> list[TropicalProduct]:
        """Fetch the authoritative PAGASA bulletin as one faithful product."""
        bulletin_url = system.data_urls.get('tropical_cyclone_bulletin') or source.url
        if not bulletin_url:
            return []
        try:
            payload = fetch_text(bulletin_url, headers={'Accept': 'text/html'}, debug=debug)
        except BackendError:
            return []
        current = _parse_pagasa_tropical_bulletin(payload, source=system.source, url=bulletin_url)
        if current is None or current.name.casefold() != system.name.casefold():
            return []
        content = _bulletin_text(payload)
        if not content:
            return []
        return [
            TropicalProduct(
                kind='advisory',
                label='Tropical Cyclone Bulletin',
                title=current.headline,
                issued_at=current.issued_at,
                content=plain_text_to_markdown(content),
                url=bulletin_url,
            )
        ]


class _PageTextParser(HTMLParser):
    """Extract readable lines from PAGASA's server-rendered bulletin page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag in {'script', 'style'}:
            self._ignored_depth += 1
            return
        if self._ignored_depth == 0 and tag in _BLOCK_TAGS:
            self._parts.append('\n')

    def handle_endtag(self, tag: str) -> None:
        if tag in {'script', 'style'} and self._ignored_depth:
            self._ignored_depth -= 1
            return
        if self._ignored_depth == 0 and tag in _BLOCK_TAGS:
            self._parts.append('\n')

    def handle_data(self, data: str) -> None:
        if self._ignored_depth == 0:
            self._parts.append(data)

    def text(self) -> str:
        """Return normalized non-empty content lines."""
        lines = [' '.join(line.split()) for line in ''.join(self._parts).splitlines()]
        return '\n'.join(line for line in lines if line)


class _BulletinTextParser(HTMLParser):
    """Extract only PAGASA's server-rendered bulletin article container."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._capture_depth = 0
        self._ignored_depth = 0
        self.found = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag in {'script', 'style'}:
            self._ignored_depth += 1
            return
        if tag == 'div':
            if self._capture_depth:
                self._capture_depth += 1
            elif 'article-content' in (attributes.get('class') or '').split():
                self._capture_depth = 1
                self.found = True
        if self._capture_depth and self._ignored_depth == 0 and tag in _BLOCK_TAGS:
            self._parts.append('\n')

    def handle_endtag(self, tag: str) -> None:
        if tag in {'script', 'style'} and self._ignored_depth:
            self._ignored_depth -= 1
            return
        if self._capture_depth and self._ignored_depth == 0 and tag in _BLOCK_TAGS:
            self._parts.append('\n')
        if tag == 'div' and self._capture_depth:
            self._capture_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._capture_depth and self._ignored_depth == 0:
            self._parts.append(data)

    def text(self) -> str:
        """Return normalized non-empty bulletin lines."""
        lines = [' '.join(line.split()) for line in ''.join(self._parts).splitlines()]
        return '\n'.join(line for line in lines if line)


def _parse_pagasa_tropical_bulletin(
    payload: str,
    *,
    source: str,
    url: str,
) -> TropicalSystem | None:
    """Normalize PAGASA's active public bulletin page without using archives."""
    text = _page_text(payload)
    if not text or _NO_ACTIVE_RE.search(text):
        return None

    system_match = _SYSTEM_RE.search(text)
    if system_match is None:
        return None

    classification = _canonical_classification(system_match.group('classification'))
    name = system_match.group('name').upper()
    issued_at = _parse_pagasa_time(_ISSUED_RE.search(text))
    bulletin_number = _group(_BULLETIN_RE.search(text), 'number')
    center_lat, center_lon = _coordinates(text)
    movement = _group(_MOVEMENT_RE.search(text), 'movement')
    max_wind = _wind(text)
    min_pressure = _group(_PRESSURE_RE.search(text), 'pressure')
    wind_extent = _group(_EXTENT_RE.search(text), 'extent')
    headline = _pagasa_headline(text)

    parameters: dict[str, list[str]] = {}
    if bulletin_number:
        parameters['PAGASA Bulletin Number'] = [bulletin_number]
    if issued_at:
        parameters['PAGASA Issue Time'] = [issued_at.isoformat()]
    if headline:
        parameters['PAGASA Bulletin Headline'] = [headline]
    if wind_extent:
        parameters['PAGASA Tropical Cyclone Wind Extent'] = [wind_extent]

    identifier = f'PAGASA-{name}-{issued_at.year}' if issued_at else f'PAGASA-{name}'
    return TropicalSystem(
        id=identifier,
        source=source,
        classification=classification,
        name=name,
        headline=headline or f'{classification}: {name}',
        basin='Northwest Pacific / Philippine Area of Responsibility',
        url=url,
        issued_at=issued_at,
        advisory_number=bulletin_number,
        center_lat=center_lat,
        center_lon=center_lon,
        movement=movement,
        min_pressure=min_pressure,
        max_wind=max_wind,
        summary=f'PAGASA current tropical-cyclone bulletin for {name}.',
        data_urls={'tropical_cyclone_bulletin': url},
        parameters=parameters,
    )


def _page_text(payload: str) -> str:
    parser = _PageTextParser()
    try:
        parser.feed(payload)
        parser.close()
    except (ValueError, AssertionError):
        return ''
    return parser.text()


def _bulletin_text(payload: str) -> str:
    """Return the bulletin article, with a fixture/legacy-page fallback."""
    parser = _BulletinTextParser()
    try:
        parser.feed(payload)
        parser.close()
    except (ValueError, AssertionError):
        return ''
    return parser.text() if parser.found else _page_text(payload)


def _canonical_classification(value: str) -> str:
    return ' '.join(word.capitalize() for word in value.split())


def _parse_pagasa_time(match: re.Match[str] | None) -> datetime | None:
    if match is None:
        return None
    time_text = re.sub(r'\.', '', match.group('time')).upper().replace(' ', '')
    try:
        return datetime.strptime(f'{time_text} {match.group("date")}', '%I:%M%p %d %B %Y').replace(
            tzinfo=_PHILIPPINE_TIME
        )
    except ValueError:
        return None


def _coordinates(text: str) -> tuple[float | None, float | None]:
    match = _COORDINATE_RE.search(text)
    if match is None:
        return None, None
    lat = float(match.group('lat'))
    lon = float(match.group('lon'))
    if match.group('lat_hemisphere').upper() == 'S':
        lat = -lat
    if match.group('lon_hemisphere').upper() == 'W':
        lon = -lon
    return lat, lon


def _wind(text: str) -> str | None:
    match = _WIND_RE.search(text)
    if match:
        return f'{_measurement(match.group("wind"))} (gust {_measurement(match.group("gust"))})'
    match = _WIND_WITHOUT_GUST_RE.search(text)
    return _measurement(match.group('wind')) if match else None


def _measurement(value: str) -> str:
    return ' '.join(value.split())


def _pagasa_headline(text: str) -> str | None:
    lines = text.splitlines()
    issued_index = next((index for index, line in enumerate(lines) if _ISSUED_RE.search(line)), -1)
    for line in lines[issued_index + 1 :]:
        upper = line.upper()
        if len(line) < 20 or upper.startswith(('VALID FOR ', 'LOCATION OF ', 'INTENSITY', 'PRESENT MOVEMENT', 'EXTENT ')):
            continue
        if sum(character.isalpha() for character in line) >= 12:
            return line
    return None


def _group(match: re.Match[str] | None, name: str) -> str | None:
    if match is None:
        return None
    value = match.group(name).strip()
    return value or None
