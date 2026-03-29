


#AXA_IA/__axa/agent_cv/config/settings.py

AVAILABLE_SITES = [
    "hellowork_jobs",
    "site_A",
    "site_B",
    "booking"
]

SITE_CONFIGS = {
    "hellowork_jobs": {
        "type": "web",
        "url": "https://www.hellowork.com/fr-fr/emploi/mot-cle_{query_slug}.html",
        "search_mode": "path_slug",
        "results": "body",
    },
    "site_A": {
        "type": "web",
        "url": "https://example.com",
        "search_input": "input[name='q']",
        "search_submit": None,
        "request_query_param": "q",
        "results": ".results",
    },
    "site_B": {
        "type": "web",
        "url": "https://example.org",
        "search_input": "#search",
        "search_submit": None,
        "request_query_param": "q",
        "results": ".list",
    },
    "booking": {
        "type": "web",
        "url": "https://www.booking.com/",
        "search_input": 'input[name="ss"]',
        "search_submit": 'button[type="submit"]',
        "request_query_param": "ss",
        "results": 'body',
    },
}
