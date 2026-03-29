

#AXA_IA/__axa/agent_cv/agent/router.py

from __future__ import annotations

from typing import List, Dict, Any


class Router:
    SUPPORTED_MODES = {"Recherche", "Analyse incident"}

    def __init__(self, available_sources: List[str] | None = None) -> None:
        self.available_sources = available_sources or []

    def validate_mode(self, mode: str) -> str:
        if mode not in self.SUPPORTED_MODES:
            raise ValueError(
                f"Mode non supporté: {mode}. "
                f"Modes disponibles: {sorted(self.SUPPORTED_MODES)}"
            )
        return mode

    def resolve_sources(self, requested_sources: List[str]) -> List[str]:
        if not requested_sources:
            return []

        if not self.available_sources:
            return requested_sources

        valid_sources = [
            source for source in requested_sources
            if source in self.available_sources
        ]
        return valid_sources

    def build_plan(self, query: str, mode: str, requested_sources: List[str]) -> Dict[str, Any]:
        validated_mode = self.validate_mode(mode)
        resolved_sources = self.resolve_sources(requested_sources)

        if not resolved_sources:
            raise ValueError("Aucune source valide sélectionnée.")

        strategy = "incident_pipeline" if validated_mode == "Analyse incident" else "search_pipeline"
        tools = self._select_tools(mode=validated_mode, sources=resolved_sources)

        return {
            "query": query.strip(),
            "mode": validated_mode,
            "sources": resolved_sources,
            "strategy": strategy,
            "tools": tools,
        }

    def _select_tools(self, mode: str, sources: List[str]) -> List[str]:
        tools: List[str] = []

        for source in sources:
            source_lower = source.lower()

            if source_lower.startswith("http://") or source_lower.startswith("https://"):
                tools.append("playwright")
            elif "site" in source_lower or "web" in source_lower:
                tools.append("playwright")
            elif "sql" in source_lower or "db" in source_lower or "database" in source_lower:
                tools.append("sql")
            elif "file" in source_lower or "pdf" in source_lower or "excel" in source_lower:
                tools.append("files")
            else:
                tools.append("generic_source")

        if mode == "Analyse incident" and "incident_analyzer" not in tools:
            tools.append("incident_analyzer")

        if "ollama" not in tools:
            tools.append("ollama")

        return list(dict.fromkeys(tools))

    def detect_intent(self, query: str, llm) -> str:
        response = llm.analyze(query).lower()

        if any(word in response for word in ["incident", "anomalie", "erreur", "failure"]):
            return "incident_pipeline"

        return "search_pipeline"













