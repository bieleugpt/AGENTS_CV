import json
import re
import subprocess
import sys
import time
from html import unescape
from pathlib import Path
from typing import Any
from uuid import uuid4

import requests

from config.settings import SITE_CONFIGS

try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
except ModuleNotFoundError:
    PlaywrightTimeoutError = TimeoutError
    sync_playwright = None


class PlaywrightTool:
    def __init__(self, headless: bool = True):
        self.headless = headless
        self._sessions_root = Path(__file__).resolve().parents[2] / ".interactive_sessions"
        self._worker_script = Path(__file__).with_name("interactive_worker.py")
        self._sessions_root.mkdir(parents=True, exist_ok=True)

    def search(self, query: str, site: str) -> str:
        """
        Retourne un texte exploitable pour le LLM.
        - si `site` est une cle de config : navigation pilotee
        - si `site` est une URL brute : simple extraction de page
        """
        if sync_playwright is None:
            return self._fallback_request_search(
                query=query,
                site=site,
                reason="playwright n'est pas installe",
            )

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=self.headless)
                page = browser.new_page(user_agent=self._default_user_agent())

                if site.startswith(("http://", "https://")):
                    result = self._scrape_direct_url(page, site)
                else:
                    result = self._search_configured_site(page, query, site)

                browser.close()
                return result
        except PermissionError as exc:
            return self._fallback_request_search(
                query=query,
                site=site,
                reason=(
                    "Permission refusee au lancement du navigateur. "
                    f"Details: {str(exc)}"
                ),
            )
        except Exception as exc:
            details = str(exc).strip() or repr(exc)
            if "NotImplementedError" in details:
                return self._fallback_request_search(
                    query=query,
                    site=site,
                    reason=details,
                )
            return f"[PLAYWRIGHT ERROR] {details}"

    def start_interactive_session(self, query: str, site: str) -> dict[str, Any]:
        if sync_playwright is None:
            return {
                "ok": False,
                "message": "Playwright n'est pas installe pour le mode interactif.",
            }

        session_id = str(uuid4())
        session_dir = self._session_dir(session_id)
        session_dir.mkdir(parents=True, exist_ok=True)

        startup_path = session_dir / "startup.json"
        state_path = session_dir / "state.json"

        startup_payload = {
            "session_id": session_id,
            "site": site,
            "query": query,
        }
        startup_path.write_text(json.dumps(startup_payload, ensure_ascii=True), encoding="utf-8")

        popen_kwargs: dict[str, Any] = {
            "args": [sys.executable, str(self._worker_script), str(session_dir)],
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "cwd": str(Path(__file__).resolve().parents[2]),
        }
        if sys.platform.startswith("win"):
            popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

        try:
            subprocess.Popen(**popen_kwargs)
        except Exception as exc:
            return {
                "ok": False,
                "message": f"Impossible de lancer le worker interactif: {str(exc) or repr(exc)}",
            }

        state = self._wait_for_state(state_path, timeout_seconds=20)
        if not state:
            return {
                "ok": False,
                "message": "Le worker interactif n'a pas repondu a temps.",
            }

        if state.get("status") != "ready":
            return {
                "ok": False,
                "message": state.get("message", "Le worker interactif a echoue."),
            }

        return {
            "ok": True,
            "session_id": session_id,
            "current_url": state.get("current_url"),
            "message": state.get(
                "message",
                "Session interactive ouverte. Validez la verification humaine puis continuez.",
            ),
        }

    def capture_interactive_session(self, session_id: str) -> dict[str, Any]:
        session_dir = self._session_dir(session_id)
        state_path = session_dir / "state.json"
        capture_path = session_dir / "capture.json"

        state = self._read_json(state_path)
        if not state:
            return {
                "ok": False,
                "message": "Session interactive introuvable ou expiree.",
            }
        if state.get("status") == "error":
            return {
                "ok": False,
                "message": state.get("message", "Le worker interactif est en erreur."),
            }

        if capture_path.exists():
            capture_path.unlink()

        self._write_command(session_dir=session_dir, command={"action": "capture"})
        captured = self._wait_for_json(capture_path, timeout_seconds=30)
        if not captured:
            latest_state = self._read_json(state_path) or {}
            return {
                "ok": False,
                "message": latest_state.get(
                    "message",
                    "Aucune capture recue depuis la session interactive.",
                ),
            }

        return {
            "ok": True,
            "source": captured["source"],
            "source_kind": captured["source_kind"],
            "status": captured["status"],
            "content": captured["content"],
        }

    def close_interactive_session(self, session_id: str) -> None:
        session_dir = self._session_dir(session_id)
        if not session_dir.exists():
            return

        self._write_command(session_dir=session_dir, command={"action": "close"})
        time.sleep(1)

    def _scrape_direct_url(self, page: Any, url: str) -> str:
        page.goto(url, timeout=60000, wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        return self._extract_page_content(page, url)

    def _search_configured_site(self, page: Any, query: str, site: str) -> str:
        self._prepare_configured_site(page, query, site)
        return self._extract_page_content(page, site)

    def _prepare_configured_site(self, page: Any, query: str, site: str) -> None:
        config = SITE_CONFIGS.get(site)
        if not config:
            raise ValueError(f"Aucune configuration trouvee pour la source '{site}'")

        url = self._resolve_configured_url(query=query, site=site, config=config)
        search_input = config.get("search_input")
        search_submit = config.get("search_submit")

        page.goto(url, timeout=60000, wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle")
        time.sleep(2)

        self._accept_cookies_if_possible(page)

        if search_input:
            page.wait_for_selector(search_input, timeout=10000)
            page.fill(search_input, query)

            if search_submit:
                page.click(search_submit)
            else:
                page.press(search_input, "Enter")

            page.wait_for_load_state("domcontentloaded")
            time.sleep(2)

    def _extract_page_content(self, page: Any, site: str) -> str:
        config = SITE_CONFIGS.get(site, {})
        results_selector = config.get("results", "body")

        try:
            page.wait_for_selector(results_selector, timeout=10000)
            content = page.locator(results_selector).inner_text(timeout=10000)
        except PlaywrightTimeoutError:
            content = page.locator("body").inner_text(timeout=10000)

        title = page.title()
        current_url = page.url

        if not content.strip():
            return f"[ERROR] Aucun contenu recupere pour la source '{site}'"

        return (
            f"SOURCE: {site}\n"
            f"URL FINALE: {current_url}\n"
            f"TITRE PAGE: {title}\n\n"
            f"CONTENU:\n{content[:4000]}"
        )

    def _accept_cookies_if_possible(self, page: Any) -> None:
        possible_selectors = [
            'button:has-text("Accepter")',
            'button:has-text("Tout accepter")',
            'button:has-text("Accept")',
            'button:has-text("I agree")',
            "#onetrust-accept-btn-handler",
        ]

        for selector in possible_selectors:
            try:
                if page.locator(selector).count() > 0:
                    page.click(selector, timeout=2000)
                    time.sleep(1)
                    return
            except Exception:
                continue

    def _fallback_request_search(self, query: str, site: str, reason: str) -> str:
        config = SITE_CONFIGS.get(site, {})
        candidate_urls = self._resolve_candidate_urls(query=query, site=site, config=config)
        params = self._build_request_params(query=query, site=site, config=config)
        headers = {"User-Agent": self._default_user_agent()}

        last_exc: requests.RequestException | None = None
        response = None

        for url in candidate_urls:
            try:
                response = requests.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=30,
                )
                response.raise_for_status()
                break
            except requests.RequestException as exc:
                last_exc = exc
                response = None

        if response is None:
            return (
                "[PLAYWRIGHT ERROR] "
                f"{reason}\n"
                "[REQUESTS FALLBACK ERROR] "
                f"{str(last_exc) if last_exc else 'Aucune URL candidate n a abouti.'}"
            )

        text_content = self._html_to_text(response.text)
        if site == "hellowork_jobs":
            structured_content = self._extract_hellowork_structured_content(response.text)
            if structured_content:
                text_content = structured_content

        if not text_content.strip():
            return (
                "[PLAYWRIGHT ERROR] "
                f"{reason}\n"
                "[REQUESTS FALLBACK] Aucun contenu exploitable recupere."
            )

        return (
            "[PLAYWRIGHT FALLBACK ACTIVE]\n"
            f"Cause: {reason}\n"
            f"SOURCE: {site}\n"
            f"URL FINALE: {response.url}\n"
            f"STATUS HTTP: {response.status_code}\n\n"
            f"CONTENU:\n{text_content[:20000]}"
        )

    def _session_dir(self, session_id: str) -> Path:
        return self._sessions_root / session_id

    @staticmethod
    def _resolve_configured_url(query: str, site: str, config: dict[str, Any]) -> str:
        return PlaywrightTool._resolve_candidate_urls(query=query, site=site, config=config)[0]

    @staticmethod
    def _resolve_candidate_urls(query: str, site: str, config: dict[str, Any]) -> list[str]:
        base_url = config.get("url", site)
        search_mode = config.get("search_mode")

        if search_mode != "path_slug":
            return [base_url]

        query_slug = PlaywrightTool._slugify_query(query)
        expanded_slug = PlaywrightTool._expand_job_slug(query_slug)

        candidates = [
            f"https://www.hellowork.com/fr-fr/emploi/mot-cle_{expanded_slug}.html",
            f"https://www.hellowork.com/fr-fr/emploi/metier_{expanded_slug}.html",
            f"https://www.hellowork.com/fr-fr/metiers/{expanded_slug}.html",
        ]

        if expanded_slug != query_slug:
            candidates.extend(
                [
                    f"https://www.hellowork.com/fr-fr/emploi/mot-cle_{query_slug}.html",
                    f"https://www.hellowork.com/fr-fr/emploi/metier_{query_slug}.html",
                    f"https://www.hellowork.com/fr-fr/metiers/{query_slug}.html",
                ]
            )

        deduped: list[str] = []
        for candidate in candidates:
            if candidate not in deduped:
                deduped.append(candidate)
        return deduped

    @staticmethod
    def _build_request_params(query: str, site: str, config: dict[str, Any]) -> dict[str, str]:
        if site.startswith(("http://", "https://")):
            return {}

        query_param = config.get("request_query_param")
        if not query_param:
            return {}

        return {query_param: query}

    @staticmethod
    def _html_to_text(html: str) -> str:
        cleaned = re.sub(r"(?is)<script.*?>.*?</script>", "\n", html)
        cleaned = re.sub(r"(?is)<style.*?>.*?</style>", "\n", cleaned)
        cleaned = re.sub(
            r"(?i)</?(div|p|section|article|li|ul|ol|br|h1|h2|h3|h4|h5|h6|main|header|footer)>",
            "\n",
            cleaned,
        )
        cleaned = re.sub(r"(?s)<[^>]+>", " ", cleaned)
        cleaned = unescape(cleaned)
        cleaned = re.sub(r"\r", "\n", cleaned)
        cleaned = re.sub(r"\n\s*\n+", "\n", cleaned)
        cleaned = re.sub(r"[ \t]+", " ", cleaned)
        return cleaned.strip()

    @staticmethod
    def _extract_hellowork_structured_content(html: str) -> str:
        json_blocks = re.findall(
            r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            html,
            re.S | re.I,
        )

        offers: list[dict[str, str]] = []
        for block in json_blocks:
            try:
                payload = json.loads(block.strip())
            except Exception:
                continue
            PlaywrightTool._collect_jobposting_payload(payload, offers)

        if not offers:
            return ""

        lines = []
        for offer in offers:
            lines.extend(
                [
                    "Voir l'offre",
                    offer.get("title", ""),
                    offer.get("company", ""),
                    offer.get("location", ""),
                    offer.get("contract", ""),
                    offer.get("salary", ""),
                    offer.get("url", ""),
                    offer.get("description", ""),
                    "",
                ]
            )

        return "\n".join(line for line in lines if line is not None)

    @staticmethod
    def _collect_jobposting_payload(payload: Any, offers: list[dict[str, str]]) -> None:
        if isinstance(payload, list):
            for item in payload:
                PlaywrightTool._collect_jobposting_payload(item, offers)
            return

        if not isinstance(payload, dict):
            return

        payload_type = payload.get("@type")
        if payload_type == "JobPosting":
            offers.append(
                {
                    "title": str(payload.get("title", "")),
                    "company": str((payload.get("hiringOrganization") or {}).get("name", "")),
                    "location": PlaywrightTool._extract_job_location(payload),
                    "contract": str(payload.get("employmentType", "")),
                    "salary": PlaywrightTool._extract_job_salary(payload),
                    "url": str(payload.get("url", "")),
                    "description": PlaywrightTool._clean_description(payload.get("description", "")),
                }
            )

        for value in payload.values():
            if isinstance(value, (dict, list)):
                PlaywrightTool._collect_jobposting_payload(value, offers)

    @staticmethod
    def _extract_job_location(payload: dict[str, Any]) -> str:
        location = payload.get("jobLocation")
        if isinstance(location, list) and location:
            location = location[0]
        if isinstance(location, dict):
            address = location.get("address", {})
            if isinstance(address, dict):
                parts = [
                    str(address.get("addressLocality", "")),
                    str(address.get("postalCode", "")),
                    str(address.get("addressRegion", "")),
                ]
                return " ".join(part for part in parts if part).strip()
        return ""

    @staticmethod
    def _extract_job_salary(payload: dict[str, Any]) -> str:
        salary = payload.get("baseSalary")
        if not isinstance(salary, dict):
            return ""
        value = salary.get("value")
        if isinstance(value, dict):
            min_value = value.get("minValue")
            max_value = value.get("maxValue")
            currency = salary.get("currency", "EUR")
            if min_value and max_value:
                return f"{min_value}-{max_value} {currency}"
            if min_value:
                return f"{min_value} {currency}"
        return ""

    @staticmethod
    def _clean_description(description: Any) -> str:
        text = str(description or "")
        text = re.sub(r"(?s)<[^>]+>", " ", text)
        text = unescape(text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()[:500]

    @staticmethod
    def _default_user_agent() -> str:
        return (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        )

    @staticmethod
    def _slugify_query(query: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")

    @staticmethod
    def _expand_job_slug(query_slug: str) -> str:
        replacements = {
            "dev": "developpeur",
            "developpeuse": "developpeur",
            "développeur": "developpeur",
            "développeuse": "developpeur",
        }
        parts = [replacements.get(part, part) for part in query_slug.split("-") if part]
        return "-".join(parts)

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    @staticmethod
    def _write_command(session_dir: Path, command: dict[str, Any]) -> None:
        (session_dir / "command.json").write_text(
            json.dumps(command, ensure_ascii=True),
            encoding="utf-8",
        )

    def _wait_for_state(self, state_path: Path, timeout_seconds: int) -> dict[str, Any] | None:
        return self._wait_for_json(state_path, timeout_seconds)

    @staticmethod
    def _wait_for_json(path: Path, timeout_seconds: int) -> dict[str, Any] | None:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            if path.exists():
                try:
                    return json.loads(path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    time.sleep(0.2)
                    continue
            time.sleep(0.2)
        return None
