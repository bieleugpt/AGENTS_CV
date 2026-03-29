from __future__ import annotations

from typing import Any, Dict

from config.settings import SITE_CONFIGS


def resolve_source_kind(source: str) -> str:
    config = SITE_CONFIGS.get(source)
    if config:
        return config.get("type", "generic")

    source_lower = source.lower()
    if source_lower.startswith(("http://", "https://")):
        return "web"
    if any(token in source_lower for token in ["sql", "db", "database"]):
        return "sql"
    return "generic"


def execute_source_query(query: str, source: str, tools: Dict[str, Any]) -> Dict[str, str]:
    source_kind = resolve_source_kind(source)

    if source_kind == "web":
        content = tools["web"].search(query, source)
    elif source_kind == "sql":
        content = tools["sql"].query(query)
    else:
        content = f"[WARNING] Source non supportee: {source}"

    status = "success"
    if any(marker in content for marker in ["[ERROR]", "[PLAYWRIGHT ERROR]", "[WARNING]", "[OLLAMA ERROR]"]):
        status = "error"
    elif _looks_like_bot_block(content):
        status = "error"

    return {
        "source": source,
        "source_kind": source_kind,
        "status": status,
        "content": content,
    }


def detect_content_issue(content: str) -> str | None:
    if _looks_like_bot_block(content):
        return "Page anti-bot ou JavaScript requis"
    return None


def _looks_like_bot_block(content: str) -> bool:
    normalized = content.lower()
    patterns = [
        "javascript is disabled",
        "enable javascript",
        "not a robot",
        "verify that you're not a robot",
        "verify you are human",
        "captcha",
        "access denied",
        "bot",
    ]
    return any(pattern in normalized for pattern in patterns)
