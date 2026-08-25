"""Public package interface for weather warnings."""

from importlib.metadata import PackageNotFoundError, version

from .geocoding import geometry_from_geocodes, resolve_alert_geometry
from .models import Alert, CanonicalTropicalSystem, TropicalProduct, TropicalSystem
from .progress import WarningQueryProgress
from .query import (
    deduplicate_alerts,
    get_alert_sources_for_country,
    get_alerts_for_country,
    get_alerts_for_point,
    get_alerts_for_source,
    get_canonical_tropical_systems,
    get_native_alerts_for_point,
    get_reusable_alerts_for_country,
    get_swic_extreme_alerts,
    get_tropical_products,
    get_tropical_systems,
    get_tropical_systems_for_source,
    get_tropical_systems_near,
    group_tropical_systems,
    match_alerts_to_point,
    match_tropical_systems_to_point,
)
from .registry import LanguageNotSupportedError, UnsupportedCountryError, list_sources, list_tropical_sources
from .sources import DisplayGeography, WarningSource

try:
    __version__ = version('wevva-warnings')
except PackageNotFoundError:
    __version__ = '0.1.0'

__all__ = [
    'Alert',
    'CanonicalTropicalSystem',
    'DisplayGeography',
    'LanguageNotSupportedError',
    'TropicalSystem',
    'TropicalProduct',
    'UnsupportedCountryError',
    'WarningSource',
    'WarningQueryProgress',
    '__version__',
    'deduplicate_alerts',
    'geometry_from_geocodes',
    'get_alert_sources_for_country',
    'get_alerts_for_country',
    'get_alerts_for_point',
    'get_alerts_for_source',
    'get_canonical_tropical_systems',
    'get_native_alerts_for_point',
    'get_reusable_alerts_for_country',
    'get_swic_extreme_alerts',
    'get_tropical_products',
    'get_tropical_systems',
    'get_tropical_systems_for_source',
    'get_tropical_systems_near',
    'group_tropical_systems',
    'list_sources',
    'list_tropical_sources',
    'match_alerts_to_point',
    'match_tropical_systems_to_point',
    'resolve_alert_geometry',
]
