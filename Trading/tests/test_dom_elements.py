import re
import unittest

class TestDomDynamicBindings(unittest.TestCase):
    def test_all_js_ids_exist_in_html(self):
        with open('templates/index.html', 'r', encoding='utf-8') as f:
            html = f.read()

        with open('static/app.js', 'r', encoding='utf-8') as f:
            js = f.read()

        # Extraire tous les IDs ciblés par getElementById
        js_ids = set(re.findall(r'getElementById\(["\']([^"\']+)["\']\)', js))
        # Extraire tous les IDs déclarés dans index.html
        html_ids = set(re.findall(r'id=["\']([^"\']+)["\']', html))

        missing = sorted([jid for jid in js_ids if jid not in html_ids])
        self.assertEqual(missing, [], f"Les IDs suivants sont référencés dans app.js mais absents de index.html : {missing}")

    def test_dynamic_pillar_gauges_present(self):
        with open('templates/index.html', 'r', encoding='utf-8') as f:
            html = f.read()

        expected_gauges = [
            'pillarMacroBar',
            'pillarGeopoliticsBar',
            'pillarInstBar',
            'pillarPABar',
            'pillarMicroBar',
            'intelBullBar',
            'intelBearBar',
            'rsiFill'
        ]
        for gauge in expected_gauges:
            self.assertIn(f'id="{gauge}"', html, f"La jauge {gauge} doit être présente dans index.html")

    def test_dynamic_score_badges_present(self):
        with open('templates/index.html', 'r', encoding='utf-8') as f:
            html = f.read()

        expected_scores = [
            'pillarMacroScore',
            'pillarGeopoliticsScore',
            'pillarInstScore',
            'pillarPAScore',
            'pillarMicroScore',
            'intelConfidence',
            'intelBullProb',
            'intelBearProb'
        ]
        for score in expected_scores:
            self.assertIn(f'id="{score}"', html, f"Le score {score} doit être présent dans index.html")

if __name__ == '__main__':
    unittest.main()
