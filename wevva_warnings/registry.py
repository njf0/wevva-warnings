"""Registry helpers for sources and backend dispatch."""

from __future__ import annotations

from .backends import (
    GenericCAPBackend,
    GeoMetBackend,
    MeteoAlarmAtomBackend,
    NWSBackend,
    WarningBackend,
)
from .sources import SOURCE_BY_ID, SOURCES, WarningSource

BACKENDS: dict[str, WarningBackend] = {
    'nws': NWSBackend(),
    'geomet': GeoMetBackend(),
    'generic_cap': GenericCAPBackend(),
    'meteoalarm_atom': MeteoAlarmAtomBackend(),
}


class UnsupportedCountryError(ValueError):
    """Raised when no sources are registered for a country."""

    def __init__(self, country_code: str) -> None:
        """Initialize the exception.

        Parameters
        ----------
        country_code : str
            Country code that could not be resolved to any registered sources.

        Returns
        -------
        None
            This constructor initializes the exception instance.

        """
        self.country_code = country_code.strip().upper()
        super().__init__(f'No alert sources are registered for country code {self.country_code!r}.')


class LanguageNotSupportedError(ValueError):
    """Raised when a country has sources, but not in the requested language."""

    def __init__(self, country_code: str, lang: str, supported_languages: list[str]) -> None:
        """Initialize the exception.

        Parameters
        ----------
        country_code : str
            Country code whose sources were inspected.
        lang : str
            Requested language code that could not be matched.
        supported_languages : list[str]
            Language codes declared by the country's registered sources.

        Returns
        -------
        None
            This constructor initializes the exception instance.

        """
        self.country_code = country_code.strip().upper()
        self.lang = lang
        self.supported_languages = supported_languages
        supported = ', '.join(supported_languages) if supported_languages else 'none declared'
        super().__init__(
            f'No alert sources for country code {self.country_code!r} support language {lang!r}. '
            f'Supported languages: {supported}.'
        )


def list_sources() -> list[WarningSource]:
    """Return the built-in source registry.

    Returns
    -------
    list[WarningSource]
        All registered warning sources.

    """
    return list(SOURCES)


def get_source(source_id: str) -> WarningSource | None:
    """Return one source definition by identifier.

    Parameters
    ----------
    source_id : str
        Source identifier to look up.

    Returns
    -------
    WarningSource | None
        Matching source definition, or ``None`` if the source is not
        registered.

    """
    return SOURCE_BY_ID.get(source_id)


def get_backend(source: WarningSource) -> WarningBackend | None:
    """Return the backend instance for a source.

    Parameters
    ----------
    source : WarningSource
        Source definition whose backend should be resolved.

    Returns
    -------
    WarningBackend | None
        Backend instance for the source, or ``None`` if the backend name is
        not registered.

    """
    return BACKENDS.get(source.backend)


def get_sources_for_country(
    country_code: str,
    *,
    lang: str | None = None,
) -> list[WarningSource]:
    """Return sources for one country code.

    Parameters
    ----------
    country_code : str
        ISO 3166-1 alpha-2 country code to look up.
    lang : str | None, optional
        Optional language code used to narrow the matching sources.

    Returns
    -------
    list[WarningSource]
        Sources registered for the country and, if requested, the given
        language.

    Raises
    ------
    UnsupportedCountryError
        If no sources are registered for the supplied country code.
    LanguageNotSupportedError
        If the country has registered sources but none support the requested
        language.

    """
    normalized_country = country_code.strip().upper()
    country_sources = [source for source in SOURCES if source.country_code == normalized_country]
    if not country_sources:
        raise UnsupportedCountryError(country_code)

    normalized_lang = _normalize_lang_tag(lang)
    if not normalized_lang:
        english_sources = [source for source in country_sources if 'en' in _source_languages(source)]
        return english_sources if english_sources else [country_sources[0]]

    matching_sources = [source for source in country_sources if normalized_lang in _source_languages(source)]
    if matching_sources:
        return matching_sources

    supported_languages = sorted({language for source in country_sources for language in _source_languages(source)})
    raise LanguageNotSupportedError(normalized_country, normalized_lang, supported_languages)


def _normalize_lang_tag(lang: str | None) -> str:
    """Normalize a language tag to its base language code.

    Parameters
    ----------
    lang : str | None
        Language tag to normalize.

    Returns
    -------
    str
        Lowercase base language code such as ``en`` or ``fr``. Returns an
        empty string for missing input.

    """
    value = (lang or '').split(',', 1)[0].strip().lower()
    return value.split('-', 1)[0].split('_', 1)[0]


def _source_languages(source: WarningSource) -> list[str]:
    """Return normalized language codes declared by a source.

    Parameters
    ----------
    source : WarningSource
        Source definition whose language metadata should be inspected.

    Returns
    -------
    list[str]
        Normalized language codes declared by the source.

    """
    return [
        normalized
        for part in (source.lang or '').split(',')
        if (normalized := _normalize_lang_tag(part))
    ]
