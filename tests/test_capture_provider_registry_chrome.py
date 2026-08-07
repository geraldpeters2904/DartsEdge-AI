import unittest
from app.services.capture_provider_registry import CaptureProviderRegistry
class CaptureProviderRegistryChromeTests(unittest.TestCase):
    def test_default_registry_includes_chrome(self):
        r=CaptureProviderRegistry(); self.assertEqual(r.names(),['chrome','manual','safari']); self.assertEqual(r.get('chrome').name,'chrome')
    def test_chrome_can_be_disabled(self):
        r=CaptureProviderRegistry(include_chrome=False, include_safari=False); self.assertEqual(r.names(),['manual'])
if __name__=='__main__': unittest.main()
