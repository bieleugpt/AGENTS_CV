


#AXA_IA/__axa/agent_cv/tools/web/playwright_tool.py

from playwright.sync_api import sync_playwright
from typing import Dict


class PlaywrightTool:
    def __init__(self, headless: bool = True):
        self.headless = headless

    def search(self, query: str, site: str) -> str:
        """
        Lance une recherche sur un site donné.
        """
        config = self._get_site_config(site)

        if not config:
            return f"[ERROR] Aucun config pour {site}"

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=self.headless)
                page = browser.new_page()

                page.goto(config["url"])

                # input recherche
                page.wait_for_selector(config["search_input"])
                page.fill(config["search_input"], query)
                page.press(config["search_input"], "Enter")

                # attendre résultats
                page.wait_for_selector(config["results"])

                content = page.inner_text(config["results"])

                browser.close()
                return content[:3000]  # limite sécurité

        except Exception as e:
            return f"[PLAYWRIGHT ERROR] {str(e)}"

    # =====================================================
    # CONFIG SITES (IMPORTANT)
    # =====================================================

    def _get_site_config(self, site: str) -> Dict:
        """
        Config par site (à adapter à ton entreprise)
        """
        configs = {
            "site_A": {
                "url": "https://example.com",
                "search_input": "input[name='q']",
                "results": ".results",
            },
            "site_B": {
                "url": "https://example.org",
                "search_input": "#search",
                "results": ".list",
            },
        }

        return configs.get(site)