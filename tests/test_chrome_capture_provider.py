import unittest
from pathlib import Path
from app.services.capture_provider import CaptureRequest
from app.services.chrome_capture_provider import ChromeCaptureProvider

class FakeBrowserSession:
    def __init__(self, html): self._html=html
    def goto(self, url, *, timeout_seconds): pass
    def wait_for(self, predicate, *, timeout_seconds, description):
        if not predicate(): raise TimeoutError(description)
    def html(self): return self._html
    def title(self): return 'MODUS Match 14726'
    def current_url(self): return 'https://modussuperseries.com/match-db-stats.php?match_id=14726'
    def close(self): pass

class ChromeCaptureProviderTests(unittest.TestCase):
    def setUp(self):
        self.request=CaptureRequest(14726,'https://modussuperseries.com/match-db-stats.php?match_id=14726',Path('/tmp'),'match_14726.html','Player A','Player B')
    def test_captures_valid_page(self):
        result=ChromeCaptureProvider(browser_session=FakeBrowserSession('<html>14726 Player A Player B</html>')).capture(self.request)
        self.assertTrue(result.successful); self.assertEqual(result.provider,'chrome')
    def test_rejects_access_challenge(self):
        result=ChromeCaptureProvider(browser_session=FakeBrowserSession('<html>14726 Player A Player B Verify you are human</html>')).capture(self.request)
        self.assertTrue(result.failed); self.assertIn('access challenge', result.error)
if __name__=='__main__': unittest.main()
