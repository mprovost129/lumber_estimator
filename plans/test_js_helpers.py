import shutil
import subprocess
import unittest
from pathlib import Path

from django.test import SimpleTestCase

REPO_ROOT = Path(__file__).resolve().parent.parent
JS_TEST_FILE = REPO_ROOT / 'js_tests' / 'viewer-helpers.test.js'


@unittest.skipIf(shutil.which('node') is None, 'node is not installed')
class ViewerHelperJsTests(SimpleTestCase):
    """Bridges the node unit tests for the viewer's pure geometry/format
    helpers (plans/static/plans/viewer-helpers.js) into the Django suite, so
    one pytest run gates both languages. Run them directly with:
    node --test js_tests/viewer-helpers.test.js"""

    def test_viewer_helper_suite_passes_under_node(self):
        result = subprocess.run(
            ['node', '--test', str(JS_TEST_FILE)],
            capture_output=True, text=True, timeout=60, cwd=REPO_ROOT,
        )
        self.assertEqual(
            result.returncode, 0,
            f'node test suite failed:\n{result.stdout}\n{result.stderr}',
        )
