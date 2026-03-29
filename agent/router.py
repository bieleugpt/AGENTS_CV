from __future__ import annotations

from typing import Any, Dict, List

import config.settings as settings


class Router:
    SUPPORTED_MODES = {"Recherche", "Analyse incident"}

    def __init__(self, available_sources: List[str] | None = None) -> None:
        self.available_sources = available_sources or []

    def validate_mode(self, mode: str) -> str:
        if mode not in self.SUPPORTED_MODES:
            raise ValueError(
                f"Mode non supporte: {mode}. "
                f"Modes disponibles: {sorted(self.SUPPORTED_MODES)}"
            )
        return mode

    def resolve_sources(self, requested_sources: List[str]) -> List[str]:
        if not requested_sources:
            return []

        resolved_sources = []
        for source in requested_sources:
            if source in resolved_sources:
                continue
            resolved_sources.append(source)

        return resolved_sources

    def build_plan(self, query: str, mode: str, requested_sources: List[str]) -> Dict[str, Any]:
        validated_mode = self.validate_mode(mode)
        resolved_sources = self.resolve_sources(requested_sources)

        if not resolved_sources:
            resolved_sources = list(dict.fromkeys(requested_sources))

        if not resolved_sources:
            raise ValueError("Aucune source selectionnee.")

        return {
            "query": query.strip(),
            "mode": validated_mode,
            "sources": resolved_sources,
            "strategy": self.strategy_for_mode(validated_mode),
            "tools": self._select_tools(resolved_sources),
        }

    @staticmethod
    def strategy_for_mode(mode: str) -> str:
        return "incident_pipeline" if mode == "Analyse incident" else "search_pipeline"

    def _select_tools(self, sources: List[str]) -> List[str]:
        tools: List[str] = []

        for source in sources:
            source_kind = self._resolve_source_kind(source)

            if source_kind == "web":
                tools.append("web")
            elif source_kind == "sql":
                tools.append("sql")
            else:
                tools.append("generic_source")

        if "ollama" not in tools:
            tools.append("ollama")

        return list(dict.fromkeys(tools))

    def detect_intent(self, query: str, llm: Any) -> str:
        response = llm.analyze(query)
        if not response or response.startswith("[OLLAMA ERROR]"):
            return "search_pipeline"

        normalized = response.lower()
        if any(word in normalized for word in ["incident", "anomalie", "erreur", "failure"]):
            return "incident_pipeline"

        return "search_pipeline"

    @staticmethod
    def _resolve_source_kind(source: str) -> str:
        config = settings.SITE_CONFIGS.get(source)
        if config:
            return config.get("type", "generic")

        source_lower = source.lower()
        if source_lower.startswith(("http://", "https://")):
            return "web"
        if any(token in source_lower for token in ["sql", "db", "database"]):
            return "sql"
        return "generic"
