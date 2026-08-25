"""Conservative text-to-Markdown helpers for tropical products."""

from __future__ import annotations

from html import escape
import re

_INLINE_MARKDOWN_RE = re.compile(r'([\\`*_\[\]])')
_BLOCK_MARKDOWN_RE = re.compile(r'^(\s{0,3})([#>+-])(?=\s|$)')
_ORDERED_LIST_RE = re.compile(r'^(\s{0,3})(\d+)([.)])(?=\s)')


def plain_text_to_markdown(value: str, *, fixed_width: bool = False) -> str:
    """Represent faithful plain text as safe, line-preserving Markdown.

    Fixed-width provider products use an indented code block. Other text has
    Markdown punctuation escaped and explicit hard line breaks added. Neither
    path rewrites or summarizes the provider's words.
    """
    lines = value.replace('\r\n', '\n').replace('\r', '\n').splitlines()
    if fixed_width:
        return '\n'.join(f'    {line}' if line else '' for line in lines)

    output: list[str] = []
    for index, line in enumerate(lines):
        escaped = escape(line, quote=False)
        escaped = _INLINE_MARKDOWN_RE.sub(r'\\\1', escaped)
        escaped = _BLOCK_MARKDOWN_RE.sub(r'\1\\\2', escaped)
        escaped = _ORDERED_LIST_RE.sub(r'\1\2\\\3', escaped)
        if escaped and index < len(lines) - 1:
            escaped += '  '
        output.append(escaped)
    return '\n'.join(output)
