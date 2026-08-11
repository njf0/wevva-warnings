"""Provider backend for China Meteorological Administration tropical systems."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import math
from typing import Any

from ..models import Alert, TropicalSystem
from ..sources import WarningSource
from .base import BackendError, WarningBackend, fetch_text

_CMA_TIMEZONE = timezone(timedelta(hours=8))
_DETAIL_URL_TEMPLATE = 'https://typhoon.nmc.cn/weatherservice/typhoon/jsons/view_{internal_id}'
_WEB_URL_TEMPLATE = 'https://typhoon.nmc.cn/web.html?tid={internal_id}'
_CLASSIFICATIONS = {
    'TD': 'Tropical Depression',
    'TS': 'Tropical Storm',
    'STS': 'Severe Tropical Storm',
    'TY': 'Typhoon',
    'STY': 'Severe Typhoon',
    'SUPERTY': 'Super Typhoon',
}
_NAMELESS = {'', 'nameless', 'none', 'null'}


class CMATropicalBackend(WarningBackend):
    """Fetch current systems from the public NMC Typhoon Network data feed."""

    backend_id = 'cma_tropical'

    def fetch_alerts(
        self,
        source: WarningSource,
        *,
        lat: float | None = None,
        lon: float | None = None,
        lang: str | None = None,
        debug: bool = False,
    ) -> list[Alert]:
        """Return no ordinary alerts for CMA's tropical-system feed."""
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
        """Fetch systems marked current by the NMC Typhoon Network."""
        del lat, lon, lang
        if not source.url:
            return []

        try:
            listing = fetch_text(
                source.url,
                headers={'Accept': 'application/javascript, application/json, text/plain'},
                debug=debug,
            )
        except BackendError:
            return []

        systems: dict[str, TropicalSystem] = {}
        for internal_id in _current_system_ids(listing):
            detail_url = _DETAIL_URL_TEMPLATE.format(internal_id=internal_id)
            try:
                detail = fetch_text(
                    detail_url,
                    headers={'Accept': 'application/javascript, application/json, text/plain'},
                    debug=debug,
                )
            except BackendError:
                continue

            system = _parse_cma_tropical_detail(
                detail,
                source=source.id,
                internal_id=internal_id,
                detail_url=detail_url,
            )
            if system is None:
                continue
            previous = systems.get(system.id)
            if previous is None or _is_newer(system, previous):
                systems[system.id] = system

        return sorted(systems.values(), key=lambda system: (system.name.casefold(), system.id))


def _current_system_ids(payload: str) -> list[str]:
    """Return internal IDs for the NMC list entries marked ``start``."""
    data = _decode_jsonp_object(payload)
    entries = data.get('typhoonList') if data else None
    if not isinstance(entries, list):
        return []

    identifiers: list[str] = []
    for entry in entries:
        if not isinstance(entry, list) or len(entry) < 2:
            continue
        status = _text(entry[-1])
        internal_id = _identifier(entry[0])
        if status and status.casefold() == 'start' and internal_id:
            identifiers.append(internal_id)
    return list(dict.fromkeys(identifiers))


def _parse_cma_tropical_detail(
    payload: str,
    *,
    source: str,
    internal_id: str,
    detail_url: str,
) -> TropicalSystem | None:
    """Normalize one current NMC Typhoon Network detail response.

    The NMC endpoint is browser-facing JSONP and uses positional arrays.  This
    parser intentionally retains the native classification and compact raw
    wind-radii data in ``parameters`` instead of guessing unsupported layers.
    """
    data = _decode_jsonp_object(payload)
    tropical_cyclone = data.get('typhoon') if data else None
    if not isinstance(tropical_cyclone, list) or len(tropical_cyclone) < 9:
        return None

    status = _text(tropical_cyclone[7])
    if status is None or status.casefold() != 'start':
        return None

    detail_internal_id = _identifier(tropical_cyclone[0]) or internal_id
    english_name = _text(tropical_cyclone[1])
    chinese_name = _text(tropical_cyclone[2])
    storm_number = _identifier(tropical_cyclone[3])
    current = _latest_observation(tropical_cyclone[8])
    if current is None:
        return None

    issued_at = _parse_cma_time(_at(current, 1))
    classification_code = _text(_at(current, 3))
    classification = _classification(classification_code)
    center_lon = _coordinate(_at(current, 4), lower=-180.0, upper=180.0)
    center_lat = _coordinate(_at(current, 5), lower=-90.0, upper=90.0)
    min_pressure = _measurement(_at(current, 6), 'hPa')
    max_wind = _measurement(_at(current, 7), 'm/s')
    movement = _movement(direction=_text(_at(current, 8)), speed=_at(current, 9))

    name = _display_name(english_name, chinese_name, storm_number, detail_internal_id)
    parameters: dict[str, list[str]] = {'CMA NMC Internal ID': [detail_internal_id]}
    if storm_number:
        parameters['CMA Tropical Cyclone Number'] = [storm_number]
    if english_name:
        parameters['CMA English Name'] = [english_name]
    if chinese_name:
        parameters['CMA Chinese Name'] = [chinese_name]
    if classification_code:
        parameters['CMA Classification Code'] = [classification_code]
    if issued_at:
        parameters['CMA Analysis Time'] = [issued_at.isoformat()]

    wind_radii = _at(current, 10)
    if isinstance(wind_radii, list) and wind_radii:
        parameters['CMA Wind Radii'] = [json.dumps(wind_radii, ensure_ascii=False, separators=(',', ':'))]

    forecast_agencies = _at(current, 11)
    if isinstance(forecast_agencies, dict):
        agencies = sorted(key for key in forecast_agencies if isinstance(key, str) and key)
        if agencies:
            parameters['CMA Forecast Agencies'] = agencies

    return TropicalSystem(
        id=storm_number or detail_internal_id,
        source=source,
        classification=classification,
        name=name,
        headline=f'{classification}: {name}',
        basin='Northwest Pacific / South China Sea',
        url=_WEB_URL_TEMPLATE.format(internal_id=detail_internal_id),
        issued_at=issued_at,
        center_lat=center_lat,
        center_lon=center_lon,
        movement=movement,
        min_pressure=min_pressure,
        max_wind=max_wind,
        summary=f'China Meteorological Administration current tropical-cyclone analysis for {name}.',
        data_urls={'cma_tropical_cyclone_detail': detail_url},
        parameters=parameters,
    )


def _decode_jsonp_object(payload: str) -> dict[str, Any] | None:
    """Extract a JSON object from direct JSON or a JSONP wrapper."""
    start = payload.find('{')
    end = payload.rfind('}')
    if start < 0 or end < start:
        return None
    try:
        value = json.loads(payload[start : end + 1])
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _latest_observation(value: object) -> list[object] | None:
    """Return the newest valid current-analysis record from a detail payload."""
    if not isinstance(value, list):
        return None

    latest: tuple[datetime | None, list[object]] | None = None
    for observation in value:
        if not isinstance(observation, list) or len(observation) < 10:
            continue
        timestamp = _parse_cma_time(_at(observation, 1))
        if latest is None or (timestamp is not None and (latest[0] is None or timestamp > latest[0])):
            latest = (timestamp, observation)
    return latest[1] if latest else None


def _parse_cma_time(value: object) -> datetime | None:
    """Parse the NMC Beijing-time ``YYYYmmddHHMM`` timestamp."""
    text = _text(value)
    if text is None:
        return None
    try:
        return datetime.strptime(text, '%Y%m%d%H%M').replace(tzinfo=_CMA_TIMEZONE)
    except ValueError:
        return None


def _classification(code: str | None) -> str:
    if code is None:
        return 'Tropical System'
    return _CLASSIFICATIONS.get(code.upper(), code)


def _display_name(
    english_name: str | None,
    chinese_name: str | None,
    storm_number: str | None,
    internal_id: str,
) -> str:
    if english_name and english_name.casefold() not in _NAMELESS:
        return english_name
    if chinese_name:
        return chinese_name
    return storm_number or internal_id


def _movement(*, direction: str | None, speed: object) -> str | None:
    speed_text = _measurement(speed, 'km/h')
    if speed_text and direction:
        return f'{speed_text} toward {direction}'
    return speed_text or (f'Toward {direction}' if direction else None)


def _measurement(value: object, unit: str) -> str | None:
    text = _text(value)
    return f'{text} {unit}' if text is not None else None


def _coordinate(value: object, *, lower: float, upper: float) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or not lower <= number <= upper:
        return None
    return number


def _identifier(value: object) -> str | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return _text(value)


def _text(value: object) -> str | None:
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, float) and math.isfinite(value):
        return str(int(value)) if value.is_integer() else str(value)
    return None


def _at(values: list[object], index: int) -> object | None:
    return values[index] if len(values) > index else None


def _is_newer(candidate: TropicalSystem, previous: TropicalSystem) -> bool:
    if candidate.issued_at is not None and previous.issued_at is not None:
        return candidate.issued_at > previous.issued_at
    return candidate.issued_at is not None
