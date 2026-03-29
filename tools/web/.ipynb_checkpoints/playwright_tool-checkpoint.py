


#AXA_IA/__axa/agent_cv/tools/web/playwright_tool.py

from playwright.sync_api import sync_playwright
from typing import Dict
import time


class PlaywrightTool:
    def __init__(self, headless: bool = True):
        self.headless = headless

    '''
    def search(self, query: str, site: str) -> str:
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=self.headless)
                page = browser.new_page()

                # CAS URL directe
                if site.startswith("http"):
                    page.goto(site, timeout=60000)
                    time.sleep(3)
                    content = page.inner_text("body")

                else:
                    config = self._get_site_config(site)
                    if not config:
                        return f"[ERROR] Aucun config pour {site}"

                    page.goto(config["url"], timeout=60000)

                    page.wait_for_selector(config["search_input"], timeout=10000)
                    page.fill(config["search_input"], query)
                    page.press(config["search_input"], "Enter")

                    page.wait_for_selector(config["results"], timeout=10000)
                    content = page.inner_text(config["results"])

                browser.close()

                return content[:3000]

        except Exception as e:
            return f"[PLAYWRIGHT ERROR] {str(e)}"
        '''






    
    
    def search(self, query: str, site: str) -> str:
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False)  # 👈 important pour debug
                page = browser.new_page()
    
                # User agent réaliste
                page.set_extra_http_headers({
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                })
    
                page.goto(site, timeout=60000)
    
                # attendre chargement réel
                page.wait_for_load_state("networkidle")
    
                time.sleep(5)
    
                # 👇 récup texte visible
                content = page.inner_text("body")
    
                browser.close()
    
                if not content.strip():
                    return "[ERROR] Aucun contenu récupéré"
    
                return content[:3000]
    
        except Exception as e:
            return f"[PLAYWRIGHT ERROR] {str(e)}"
    
    



        

    def _get_site_config(self, site: str) -> Dict:
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

        