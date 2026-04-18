"""Public package interface for weather warnings."""

from importlib.metadata import PackageNotFoundError, version

from .geocoding import geometry_from_geocodes, resolve_alert_geometry
from .models import Alert
from .query import get_alerts_for_point, get_alerts_for_source
from .registry import LanguageNotSupportedError, UnsupportedCountryError, list_sources, list_v2_sources
from .sources import WarningSource

try:
    __version__ = version('wevva-warnings')
except PackageNotFoundError:
    __version__ = '0.1.0'

__all__ = [
    'Alert',
    'LanguageNotSupportedError',
    'UnsupportedCountryError',
    'WarningSource',
    '__version__',
    'geometry_from_geocodes',
    'get_alerts_for_point',
    'get_alerts_for_source',
    'list_sources',
    'list_v2_sources',
    'resolve_alert_geometry',
]
