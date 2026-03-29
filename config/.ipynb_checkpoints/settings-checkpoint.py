


#AXA_IA/__axa/agent_cv/config/settings.py

AVAILABLE_SITES = [
    "site_A",
    "site_B",
    "booking"
]

SITE_CONFIGS = {
    "site_A": {
        "type": "web",
        "url": "https://example.com",
        "search_input": "input[name='q']",
        "search_submit": None,
        "results": ".results",
    },
    "site_B": {
        "type": "web",
        "url": "https://example.org",
        "search_input": "#search",
        "search_submit": None,
        "results": ".list",
    },
    "booking": {
        "type": "web",
        "url": "https://www.booking.com/",
        "search_input": 'input[name="ss"]',
        "search_submit": 'button[type="submit"]',
        "results": 'body',
    },
}

