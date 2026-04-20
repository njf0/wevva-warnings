"""Tests for shared backend HTTP helpers."""

from __future__ import annotations

import subprocess
import unittest
from unittest.mock import patch
from urllib.error import URLError

from wevva_warnings.backends.base import fetch_text


class BaseFetchTests(unittest.TestCase):
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
