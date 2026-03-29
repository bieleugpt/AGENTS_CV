import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config.settings import SITE_CONFIGS
from tools.web.playwright_tool import PlaywrightTool

try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
except ModuleNotFoundError:
    PlaywrightTimeoutError = TimeoutError
    sync_playwright = None


def main() -> int:
    if len(sys.argv) != 2:
        return 1

    session_dir = Path(sys.argv[1])
    state_path = session_dir / "state.json"

    try:
        startup = read_json(session_dir / "startup.json")
        if not startup:
            write_json(
                state_path,
                {"status": "error", "message": "Startup introuvable pour la session interactive."},
            )
            return 1

        if sync_playwright is None:
            write_json(
                state_path,
                {"status": "error", "message": "Playwright n'est pas installe dans cet environnement."},
            )
            return 1

        site = startup["site"]
        query = startup["query"]

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=False)
            context = browser.new_context(user_agent=PlaywrightTool._default_user_agent())
            page = context.new_page()

            if site.startswith(("http://", "https://")):
                page.goto(site, timeout=60000, wait_until="domcontentloaded")
            else:
                prepare_configured_site(page=page, query=query, site=site)

            write_json(
                state_path,
                {
                    "status": "ready",
                    "message": (
                        "Session interactive ouverte. Validez la verification humaine "
                        "dans le navigateur, puis revenez cliquer sur Continuer."
                    ),
                    "current_url": page.url,
                },
            )

            loop_until_closed(session_dir=session_dir, page=page, site=site)
            try:
                context.close()
            except Exception:
                pass
            try:
                browser.close()
            except Exception:
                pass
    except Exception as exc:
        details = str(exc).strip() or repr(exc)
        write_json(
            state_path,
            {"status": "error", "message": f"Impossible d'ouvrir la session interactive: {details}"},
        )
        return 1

    return 0


def loop_until_closed(session_dir: Path, page: Any, site: str) -> None:
    command_path = session_dir / "command.json"
    capture_path = session_dir / "capture.json"
    state_path = session_dir / "state.json"

    while True:
        if command_path.exists():
            command = read_json(command_path) or {}
            try:
                command_path.unlink()
            except Exception:
                pass

            action = command.get("action")
            if action == "capture":
                capture = build_capture_payload(page=page, site=site)
                write_json(capture_path, capture)
                write_json(
                    state_path,
                    {
                        "status": "ready",
                        "message": "Capture terminee." if capture["status"] == "success" else "Capture terminee avec erreur exploitable.",
                        "current_url": page.url,
                    },
                )
            elif action == "close":
                write_json(
                    state_path,
                    {"status": "closed", "message": "Session interactive fermee."},
                )
                return

        time.sleep(0.2)


def build_capture_payload(page: Any, site: str) -> dict[str, str]:
    try:
        page.wait_for_load_state("domcontentloaded", timeout=10000)
        time.sleep(1)
        return {
            "source": site,
            "source_kind": "web",
            "status": "success",
            "content": extract_page_content(page, site),
        }
    except Exception as exc:
        details = str(exc).strip() or repr(exc)
        return {
            "source": site,
            "source_kind": "web",
            "status": "error",
            "content": f"[PLAYWRIGHT ERROR] {details}",
        }


def prepare_configured_site(page: Any, query: str, site: str) -> None:
    config = SITE_CONFIGS.get(site)
    if not config:
        raise ValueError(f"Aucune configuration trouvee pour la source '{site}'")

    url = config["url"]
    search_input = config.get("search_input")
    search_submit = config.get("search_submit")

    page.goto(url, timeout=60000, wait_until="domcontentloaded")
    page.wait_for_load_state("networkidle")
    time.sleep(2)

    accept_cookies_if_possible(page)

    if search_input:
        page.wait_for_selector(search_input, timeout=10000)
        page.fill(search_input, query)

        if search_submit:
            page.click(search_submit)
        else:
            page.press(search_input, "Enter")

        page.wait_for_load_state("domcontentloaded")
        time.sleep(2)


def extract_page_content(page: Any, site: str) -> str:
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


def accept_cookies_if_possible(page: Any) -> None:
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


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
