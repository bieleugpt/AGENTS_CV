

#AXA_IA/__axa/agent_cv/agent/orchestrator.py

from __future__ import annotations

from typing import List, Dict, Any

from utils.logger import get_logger
from agent.router import Router
from pipelines.search_pipeline import SearchPipeline
from pipelines.incident_pipeline import IncidentPipeline
from llm.ollama_client import OllamaClient
from tools.sql.sql_tool import SQLTool
from tools.web.playwright_tool import PlaywrightTool
from config.settings import AVAILABLE_SITES


logger = get_logger(__name__)


class AgentOrchestrator:
    """
    Orchestrateur principal.
    """

    def __init__(self, available_sources: List[str] | None = None) -> None:
        self.available_sources = available_sources or AVAILABLE_SITES
        self.router = Router(available_sources=self.available_sources)
        self.llm = OllamaClient()

        self.tools = {
            "web": PlaywrightTool(),
            "sql": SQLTool(),
        }

    def run(self, query: str, mode: str, sources: List[str]) -> Dict[str, Any]:
        logger.info(f"Query reçue: {query}")
        logger.info(f"Mode: {mode}")
        logger.info(f"Sources: {sources}")

        cleaned_query = self._clean_query(query)

        if not cleaned_query:
            return self._empty_response("La requête est vide après nettoyage.")

        try:
            plan = self.router.build_plan(
                query=cleaned_query,
                mode=mode,
                requested_sources=sources,
            )

            detected_strategy = self.router.detect_intent(cleaned_query, self.llm)
            plan["strategy"] = detected_strategy

            logger.info(f"Plan généré: {plan}")

        except ValueError as exc:
            logger.exception("Erreur lors de la construction du plan")
            return self._error_response(str(exc), sources=sources)

        if plan["strategy"] == "search_pipeline":
            pipeline = SearchPipeline(self.tools, self.llm)
        elif plan["strategy"] == "incident_pipeline":
            pipeline = IncidentPipeline(self.tools, self.llm)
        else:
            return self._error_response("Stratégie inconnue", sources=sources)

        return pipeline.run(
            query=plan["query"],
            sources=plan["sources"],
        )

    @staticmethod
    def _clean_query(query: str) -> str:
        return " ".join(query.split()).strip()

    @staticmethod
    def _empty_response(message: str) -> Dict[str, Any]:
        return {
            "summary": message,
            "data": [],
            "issues": ["Requête vide"],
            "analysis": "Aucune exécution effectuée.",
            "sources": [],
            "mode": None,
            "strategy": None,
            "tools_used": [],
        }

    @staticmethod
    def _error_response(message: str, sources: List[str] | None = None) -> Dict[str, Any]:
        return {
            "summary": "Erreur de routage",
            "data": [],
            "issues": [message],
            "analysis": "Le routeur n'a pas pu construire un plan valide.",
            "sources": sources or [],
            "mode": None,
            "strategy": None,
            "tools_used": [],
        }


def run_agent(query: str, mode: str, sources: List[str]) -> Dict[str, Any]:
    orchestrator = AgentOrchestrator()
    return orchestrator.run(query=query, mode=mode, sources=sources)



    