"""Command-line interface for weather warnings."""

from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import contextmanager
from typing import Iterator, TypeVar

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.pretty import Pretty
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich.text import Text

from ._debug import bind_progress_callback
from .models import Alert, TropicalSystem
from .query import (
    get_alerts_for_country,
    get_alerts_for_point,
    get_alerts_for_source,
    get_tropical_systems_for_source,
    get_tropical_systems_near,
)
from .registry import UnsupportedCountryError, get_source, list_sources
from .sources import WarningSource

app = typer.Typer(
    add_completion=False,
    help='Retrieve official weather warnings and tropical-system products from built-in sources.',
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)
console = Console()
_VALID_SOURCE_KINDS = {'alert', 'tropical_system'}
_T = TypeVar('_T')


@app.command(context_settings={'ignore_unknown_options': True})
def point(
    lat: float = typer.Argument(..., help='Latitude in decimal degrees.'),
    lon: float = typer.Argument(..., help='Longitude in decimal degrees.'),
    country_code: str = typer.Argument(..., help='ISO country code used for source routing.'),
    lang: str | None = typer.Option(None, '--lang', help='Optional language tag used for source selection.'),
    active_only: bool = typer.Option(False, '--active', '--active-only', help='Only return alerts that are active right now.'),
    debug: bool = typer.Option(False, '--debug', help='Show more progress information while fetching alerts.'),
) -> None:
    """Retrieve alerts for one point."""
    _render_point_query(
        lat,
        lon,
        country_code,
        lang=lang,
        active_only=active_only,
        debug=debug,
    )


@app.command()
def country(
    country_code: str = typer.Argument(..., help='ISO country code used for source routing.'),
    lang: str | None = typer.Option(None, '--lang', help='Optional language tag used for source selection.'),
    active_only: bool = typer.Option(False, '--active', '--active-only', help='Only return alerts that are active right now.'),
    formatted: bool = typer.Option(False, '--formatted', help='Render alerts as a table instead of pretty-printed objects.'),
    debug: bool = typer.Option(False, '--debug', help='Show progress information while fetching country candidates.'),
) -> None:
    """Retrieve reusable country-level alert candidates."""
    _render_country_query(
        country_code,
        lang=lang,
        active_only=active_only,
        formatted=formatted,
        debug=debug,
    )


@app.command()
def sources(
    kind: str | None = typer.Option(
        None,
        '--kind',
        help='Optional source kind filter: alert or tropical_system.',
    ),
) -> None:
    """List built-in warning sources."""
    normalized_kind = _normalize_source_kind(kind)
    if kind is not None and normalized_kind is None:
        typer.secho("Source kind must be 'alert' or 'tropical_system'.", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=2)

    console.print(_render_sources_table(list_sources(kind=normalized_kind)))


@app.command()
def source(
    source_id: str = typer.Argument(..., help='Built-in source identifier to query.'),
    active_only: bool = typer.Option(False, '--active', '--active-only', help='Only return alerts that are active right now.'),
    formatted: bool = typer.Option(False, '--formatted', help='Render alerts as a table instead of pretty-printed objects.'),
    debug: bool = typer.Option(False, '--debug', help='Show more progress information while fetching alerts.'),
) -> None:
    """Retrieve alerts from one source."""
    _render_source_query(
        source_id,
        active_only=active_only,
        formatted=formatted,
        debug=debug,
    )


@app.command('tropical-source')
def tropical_source(
    source_id: str = typer.Argument(..., help='Built-in tropical-system source identifier to query.'),
    formatted: bool = typer.Option(False, '--formatted', help='Render tropical systems as a table instead of pretty-printed objects.'),
    debug: bool = typer.Option(False, '--debug', help='Show more progress information while fetching tropical systems.'),
) -> None:
    """Retrieve tropical systems from one source."""
    _render_tropical_source_query(
        source_id,
        formatted=formatted,
        debug=debug,
    )


@app.command('tropical-near', context_settings={'ignore_unknown_options': True})
def tropical_near(
    lat: float = typer.Argument(..., help='Latitude in decimal degrees.'),
    lon: float = typer.Argument(..., help='Longitude in decimal degrees.'),
    radius_km: float = typer.Option(1000.0, '--radius-km', help='Maximum center distance in kilometres.'),
    source_ids: list[str] | None = typer.Option(
        None,
        '--source',
        help='Optional tropical-system source id. Can be supplied more than once.',
    ),
    formatted: bool = typer.Option(False, '--formatted', help='Render tropical systems as a table instead of pretty-printed objects.'),
    debug: bool = typer.Option(False, '--debug', help='Show more progress information while fetching tropical systems.'),
) -> None:
    """Retrieve tropical systems near one point."""
    _render_tropical_near_query(
        lat,
        lon,
        radius_km=radius_km,
        source_ids=source_ids,
        formatted=formatted,
        debug=debug,
    )


def _render_point_query(
    lat: float,
    lon: float,
    country_code: str,
    *,
    lang: str | None,
    active_only: bool,
    debug: bool,
) -> None:
    """Run the point query flow and render the result.

    Parameters
    ----------
    lat : float
        Latitude of the point to query.
    lon : float
        Longitude of the point to query.
    country_code : str
        ISO 3166-1 alpha-2 country code used for source routing.
    lang : str | None
        Optional language code used to filter sources by.
    active_only : bool
        If True, only return alerts that are currently active.
    debug : bool
        If True, show progress information while the query runs.

    Returns
    -------
    None
        This helper prints the result to the terminal.

    """
    render_console = console
    try:
        render_console, alerts = _run_with_optional_debug(
            lambda debug_enabled: get_alerts_for_point(
                lat,
                lon,
                country_code,
                lang=lang,
                debug=debug_enabled,
                active_only=active_only,
            ),
            debug=debug,
        )
    except UnsupportedCountryError as exc:
        typer.secho(str(exc), err=True, fg=typer.colors.RED)
        raise typer.Exit(code=2) from exc

    if not alerts:
        render_console.print('[bold yellow]No alerts.[/bold yellow]')
        return

    show_source = len({alert.source for alert in alerts}) > 1
    render_console.print(_render_alerts_table(alerts, show_source=show_source))


def _render_country_query(
    country_code: str,
    *,
    lang: str | None,
    active_only: bool,
    formatted: bool,
    debug: bool,
) -> None:
    """Run the country candidate query flow and render the result."""
    render_console = console
    try:
        render_console, alerts = _run_with_optional_debug(
            lambda _debug_enabled: get_alerts_for_country(
                country_code,
                lang=lang,
                active_only=active_only,
            ),
            debug=debug,
        )
    except UnsupportedCountryError as exc:
        typer.secho(str(exc), err=True, fg=typer.colors.RED)
        raise typer.Exit(code=2) from exc

    if not alerts:
        render_console.print('[bold yellow]No country-level alert candidates.[/bold yellow]')
        return

    if formatted:
        show_source = len({alert.source for alert in alerts}) > 1
        render_console.print(_render_alerts_table(alerts, show_source=show_source))
        return

    for alert in alerts:
        render_console.print(_render_alert_object(alert))


def _render_source_query(
    source_id: str,
    *,
    active_only: bool,
    formatted: bool,
    debug: bool,
) -> None:
    """Run the source query flow and render the result.

    Parameters
    ----------
    source_id : str
        Identifier of the built-in source to query.
    active_only : bool
        If True, only return alerts that are currently active.
    formatted : bool
        If True, render alerts as a table. Otherwise, pretty-print compact
        alert objects.
    debug : bool
        If True, show progress information while the query runs.

    Returns
    -------
    None
        This helper prints the result to the terminal.

    """
    if get_source(source_id) is None:
        typer.secho(f'No alert source is registered with id {source_id!r}.', err=True, fg=typer.colors.RED)
        raise typer.Exit(code=2)

    render_console, alerts = _run_with_optional_debug(
        lambda debug_enabled: get_alerts_for_source(
            source_id,
            debug=debug_enabled,
            active_only=active_only,
        ),
        debug=debug,
    )

    if not alerts:
        render_console.print('[bold yellow]No alerts.[/bold yellow]')
        return

    if formatted:
        render_console.print(_render_alerts_table(alerts, show_source=False))
        return

    for alert in alerts:
        render_console.print(_render_alert_object(alert))


def _render_tropical_source_query(
    source_id: str,
    *,
    formatted: bool,
    debug: bool,
) -> None:
    """Run the tropical-system source query flow and render the result."""
    source = get_source(source_id)
    if source is None:
        typer.secho(f'No source is registered with id {source_id!r}.', err=True, fg=typer.colors.RED)
        raise typer.Exit(code=2)
    if source.kind != 'tropical_system':
        typer.secho(
            f"Source {source_id!r} is an alert source, not a tropical-system source.",
            err=True,
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=2)

    render_console, systems = _run_with_optional_debug(
        lambda debug_enabled: get_tropical_systems_for_source(
            source_id,
            debug=debug_enabled,
        ),
        debug=debug,
    )

    if not systems:
        render_console.print('[bold yellow]No tropical systems.[/bold yellow]')
        return

    if formatted:
        render_console.print(_render_tropical_systems_table(systems))
        return

    for system in systems:
        render_console.print(_render_tropical_system_object(system))


def _render_tropical_near_query(
    lat: float,
    lon: float,
    *,
    radius_km: float,
    source_ids: list[str] | None,
    formatted: bool,
    debug: bool,
) -> None:
    """Run the tropical-system proximity query flow and render the result."""
    try:
        render_console, systems = _run_with_optional_debug(
            lambda debug_enabled: get_tropical_systems_near(
                lat,
                lon,
                radius_km=radius_km,
                source_ids=source_ids,
                debug=debug_enabled,
            ),
            debug=debug,
        )
    except ValueError as exc:
        typer.secho(str(exc), err=True, fg=typer.colors.RED)
        raise typer.Exit(code=2) from exc

    if not systems:
        render_console.print('[bold yellow]No tropical systems.[/bold yellow]')
        return

    if formatted:
        render_console.print(_render_tropical_systems_table(systems))
        return

    for system in systems:
        render_console.print(_render_tropical_system_object(system))


def main() -> None:
    """Run the CLI application.

    Returns
    -------
    None
        This function hands off execution to Typer.

    """
    app()


def _run_with_optional_debug(
    fetch: Callable[[bool], list[_T]],
    *,
    debug: bool,
) -> tuple[Console, list[_T]]:
    """Run a query function with optional debug output.

    Parameters
    ----------
    fetch : Callable[[bool], list[Alert]]
        Query function that accepts the effective debug flag.
    debug : bool
        If True, run the query inside a debug session.

    Returns
    -------
    tuple[Console, list[_T]]
        Console to render with and results returned by the query.

    """
    if not debug:
        return console, fetch(False)

    with _debug_session() as debug_console:
        results = fetch(True)
    return debug_console, results


@contextmanager
def _debug_session() -> Iterator[Console]:
    """Create a debug logging and progress session.

    Yields
    ------
    Iterator[Console]
        Rich console configured for debug output during the session.

    """
    debug_console = Console(stderr=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s',
        handlers=[
            RichHandler(
                console=debug_console,
                show_time=True,
                show_level=True,
                show_path=False,
                rich_tracebacks=False,
                log_time_format='[%H:%M:%S]',
            )
        ],
        force=True,
    )
    with Progress(
        SpinnerColumn(style='cyan'),
        TextColumn('[progress.description]{task.description}'),
        BarColumn(bar_width=None),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=debug_console,
        transient=True,
        expand=True,
    ) as progress:
        debug_progress = _DebugProgress(progress)
        with bind_progress_callback(debug_progress.emit):
            yield debug_console


class _DebugProgress:
    """Track and render debug progress for source and document fetching."""

    def __init__(self, progress: Progress) -> None:
        """Initialize the progress tracker.

        Parameters
        ----------
        progress : Progress
            Rich progress instance to update.

        Returns
        -------
        None
            This constructor initializes the tracker.

        """
        self.progress = progress
        self.sources_task_id = progress.add_task('Sources', total=1, completed=0, visible=False)
        self.documents_task_id = progress.add_task('CAP documents', total=1, completed=0, visible=False)

    def emit(self, event: str, payload: dict[str, object]) -> None:
        """Handle one progress event.

        Parameters
        ----------
        event : str
            Event name to handle.
        payload : dict[str, object]
            Event payload associated with the progress update.

        Returns
        -------
        None
            This method updates the Rich progress display in place.

        """
        if event == 'sources_total':
            total = int(payload.get('total') or 0)
            self.progress.update(
                self.sources_task_id,
                total=max(total, 1),
                completed=0,
                visible=total > 0,
                description='Sources',
            )
            return

        if event == 'source_started':
            source = str(payload.get('source') or 'source')
            self.progress.update(self.sources_task_id, description=f'Sources: {source}')
            self.progress.update(
                self.documents_task_id,
                total=1,
                completed=0,
                visible=False,
                description='CAP documents',
            )
            return

        if event in {'source_finished', 'country_source_finished'}:
            self.progress.advance(self.sources_task_id)
            self.progress.update(self.sources_task_id, description='Sources')
            self.progress.update(
                self.documents_task_id,
                total=1,
                completed=0,
                visible=False,
                description='CAP documents',
            )
            return

        if event == 'alerts_total':
            total = int(payload.get('total') or 0)
            if total <= 0:
                self.progress.update(
                    self.documents_task_id,
                    total=1,
                    completed=0,
                    visible=False,
                    description='CAP documents',
                )
                return

            source = str(payload.get('source') or 'source')
            phase = str(payload.get('phase') or 'checking')
            description = 'CAP documents' if phase == 'documents' else 'Warnings'
            self.progress.update(
                self.documents_task_id,
                total=total,
                completed=0,
                visible=True,
                description=f'{description}: {source}',
            )
            return

        if event == 'alerts_checked':
            completed = int(payload.get('completed') or 0)
            self.progress.update(self.documents_task_id, completed=completed)


def _render_alerts_table(alerts: list[Alert], *, show_source: bool) -> Table:
    """Render alerts as a Rich table.

    Parameters
    ----------
    alerts : list[Alert]
        Alerts to render.
    show_source : bool
        If True, include a source column in the output.

    Returns
    -------
    Table
        Rich table containing the supplied alerts.

    """
    table = Table(expand=True, show_lines=True)
    if show_source:
        table.add_column('Source', style='bold cyan', no_wrap=True)
    table.add_column('Headline', style='bold', ratio=2, overflow='fold')
    table.add_column('Details', ratio=4, overflow='fold')

    for alert in alerts:
        severity = alert.severity or 'Unknown'
        row: list[str | Text] = []
        if show_source:
            row.append(alert.source)
        details = Text()
        details.append('Event: ', style='bold')
        details.append(alert.event)
        details.append('\n')
        details.append('Severity: ', style='bold')
        details.append(Text(severity, style=_severity_style(severity)))
        if alert.onset is not None:
            details.append('\n')
            details.append('Onset: ', style='bold')
            details.append(alert.onset.isoformat())
        if alert.expires is not None:
            details.append('\n')
            details.append('Expires: ', style='bold')
            details.append(alert.expires.isoformat())
        if alert.description:
            details.append('\n')
            details.append('Description: ', style='bold')
            details.append(alert.description)
        row.append(Text(alert.headline, style='bold'))
        row.append(details)
        table.add_row(*row)

    return table


def _render_sources_table(sources: list[WarningSource]) -> Table:
    """Render warning sources as a Rich table.

    Parameters
    ----------
    sources : list[WarningSource]
        Source definitions to render.

    Returns
    -------
    Table
        Rich table containing the supplied sources.

    """
    table = Table(title=f'Registered Sources ({len(sources)})', expand=True, show_lines=True)
    table.add_column('ID', style='bold cyan', no_wrap=True)
    table.add_column('Kind', style='bright_magenta', no_wrap=True)
    table.add_column('Name', style='bold', overflow='fold')
    table.add_column('Backend', style='magenta', no_wrap=True)
    table.add_column('Country', style='green', no_wrap=True)
    table.add_column('URL', style='blue', overflow='fold')
    table.add_column('Lang', style='yellow', no_wrap=True)
    table.add_column('Notes', overflow='fold')

    for source in sources:
        table.add_row(
            source.id,
            source.kind,
            source.name,
            source.backend,
            source.country_code or '',
            source.url or '',
            source.lang or '',
            source.notes or '',
        )

    return table


def _render_alert_object(alert: Alert) -> Panel:
    """Render one alert as a compact Rich object preview.

    Parameters
    ----------
    alert : Alert
        Alert to render.

    Returns
    -------
    Panel
        Rich panel containing a compact pretty-printed alert view.

    """
    return Panel(
        Pretty(alert, expand_all=True, indent_guides=True),
        title=f'Alert {alert.id}',
        expand=True,
        border_style='blue',
    )


def _render_tropical_systems_table(systems: list[TropicalSystem]) -> Table:
    """Render tropical systems as a Rich table."""
    table = Table(expand=True, show_lines=True)
    table.add_column('Headline', style='bold', ratio=2, overflow='fold')
    table.add_column('Details', ratio=4, overflow='fold')

    for system in systems:
        details = Text()
        details.append('Classification: ', style='bold')
        details.append(system.classification)
        details.append('\n')
        details.append('Name: ', style='bold')
        details.append(system.name)
        if system.basin:
            details.append('\n')
            details.append('Basin: ', style='bold')
            details.append(system.basin)
        if system.issued_at is not None:
            details.append('\n')
            details.append('Issued: ', style='bold')
            details.append(system.issued_at.isoformat())
        if system.center_lat is not None and system.center_lon is not None:
            details.append('\n')
            details.append('Center: ', style='bold')
            details.append(f'{system.center_lat:.2f}, {system.center_lon:.2f}')
        if system.max_wind:
            details.append('\n')
            details.append('Max wind: ', style='bold')
            details.append(system.max_wind)
        if system.min_pressure:
            details.append('\n')
            details.append('Pressure: ', style='bold')
            details.append(system.min_pressure)
        if system.geometries:
            details.append('\n')
            details.append('Geometries: ', style='bold')
            details.append(', '.join(sorted(system.geometries)))
        if system.summary:
            details.append('\n')
            details.append('Summary: ', style='bold')
            details.append(system.summary)
        table.add_row(Text(system.headline, style='bold'), details)

    return table


def _render_tropical_system_object(system: TropicalSystem) -> Panel:
    """Render one tropical system as a compact Rich object preview."""
    return Panel(
        Pretty(system, expand_all=True, indent_guides=True),
        title=f'Tropical System {system.id}',
        expand=True,
        border_style='magenta',
    )


def _normalize_source_kind(kind: str | None) -> str | None:
    """Return a normalized source kind if valid."""
    if kind is None:
        return None

    normalized = kind.strip().lower().replace('-', '_')
    if normalized not in _VALID_SOURCE_KINDS:
        return None
    return normalized


def _severity_style(severity: str) -> str:
    """Return the Rich style to use for a severity label.

    Parameters
    ----------
    severity : str
        Severity value to map to a style.

    Returns
    -------
    str
        Rich style string for the supplied severity.

    """
    normalized = severity.strip().lower()
    return {
        'extreme': 'bold bright_red',
        'severe': 'bold red',
        'moderate': 'bold yellow',
        'minor': 'bold cyan',
    }.get(normalized, 'bold white')
