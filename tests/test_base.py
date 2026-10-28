"""Tests for shared backend HTTP helpers."""

from __future__ import annotations

import subprocess
import unittest
from email.message import Message
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from wevva_warnings.backends.base import ETagCachingSession, fetch_text


class _Response:
    def __init__(self, body: bytes, *, etag: str) -> None:
        self._body = body
        self.headers = Message()
        self.headers['Content-Type'] = 'application/xml; charset=utf-8'
        self.headers['ETag'] = etag

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_: object) -> None:
        return None


class BaseFetchTests(unittest.TestCase):
    def test_etag_session_reuses_cached_xml_after_304(self) -> None:
        session = ETagCachingSession(max_entries=2)
        not_modified = HTTPError(
            'https://example.com/alert.xml',
            304,
            'Not Modified',
            Message(),
            None,
        )

        with patch.object(
            session._opener,
            'open',
            side_effect=[_Response(b'<alert>cached</alert>', etag='"fixture-etag"'), not_modified],
        ) as open_request:
            first = session.fetch_text('https://example.com/alert.xml')
            second = session.fetch_text('https://example.com/alert.xml')

        self.assertEqual(first, '<alert>cached</alert>')
        self.assertEqual(second, first)
        first_request = open_request.call_args_list[0].args[0]
        second_request = open_request.call_args_list[1].args[0]
        self.assertIsNone(first_request.get_header('If-none-match'))
        self.assertEqual(second_request.get_header('If-none-match'), '"fixture-etag"')

    def test_fetch_text_falls_back_to_curl_when_urllib_fails(self) -> None:
        completed = subprocess.CompletedProcess(
            args=['curl'],
            returncode=0,
            stdout='hello from curl'.encode('utf-8'),
            stderr=b'',
        )

        with (
            patch('wevva_warnings.backends.base.urlopen', side_effect=URLError('Temporary failure in name resolution')),
            patch('wevva_warnings.backends.base.shutil.which', return_value='/usr/bin/curl'),
            patch('wevva_warnings.backends.base.subprocess.run', return_value=completed) as run,
        ):
            payload = fetch_text(
                'https://example.com/feed.xml',
                headers={'Accept': 'application/xml'},
            )

        self.assertEqual(payload, 'hello from curl')
        command = run.call_args.args[0]
        self.assertIn('-fsSL', command)
        self.assertIn('https://example.com/feed.xml', command)
        self.assertIn('Accept: application/xml', command)


if __name__ == '__main__':
    unittest.main()
