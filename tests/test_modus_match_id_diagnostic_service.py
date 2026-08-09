import unittest

from app.services.modus_match_id_diagnostic_service import (
    _match_ids_from_html,
    _sample_links_from_html,
)


class ModusMatchIdDiagnosticServiceTests(unittest.TestCase):
    def test_extracts_match_ids_from_html(self):
        html = '''
        <a href="match-db-stats.php?match_id=1234">A</a>
        <a href="/match-db-stats.php?match_id=5678">B</a>
        '''

        self.assertEqual(
            _match_ids_from_html(html),
            (1234, 5678),
        )

    def test_sample_links_returns_unique_links(self):
        html = '''
        <a href="match-db-stats.php?match_id=1234">A</a>
        <a href="match-db-stats.php?match_id=1234">A2</a>
        '''

        links = _sample_links_from_html(html)
        self.assertEqual(len(links), 1)


if __name__ == "__main__":
    unittest.main()
