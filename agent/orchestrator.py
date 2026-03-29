from __future__ import annotations

from typing import Any, Dict, List

from agent.router import Router
import config.settings as settings
from llm.ollama_client import OllamaClient
from pipelines.incident_pipeline import IncidentPipeline
from pipelines.search_pipeline import SearchPipeline
from tools.sql.sql_tool import SQLTool
from tools.web.playwright_tool import PlaywrightTool
from utils.logger import get_logger


logger = get_logger(__name__)


class AgentOrchestrator:
    """Orchestrateur principal."""

    def __init__(self, available_sources: List[str] | None = None) -> None:
        self.available_sources = available_sources or settings.AVAILABLE_SITES
        self.router = Router(available_sources=self.available_sources)
        self.llm = OllamaClient()
        self.tools = {
            "web": PlaywrightTool(),
            "sql": SQLTool(),
        }

    def run(self, query: str, mode: str, sources: List[str]) -> Dict[str, Any]:
        return self._run_internal(query=query, mode=mode, sources=sources)

    def run_with_prefetched_results(
        self,
        query: str,
        mode: str,
        sources: List[str],
        raw_results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        return self._run_internal(
            query=query,
            mode=mode,
            sources=sources,
            raw_results=raw_results,
        )

    def _run_internal(
        self,
        query: str,
        mode: str,
        sources: List[str],
        raw_results: List[Dict[str, Any]] | None = None,
    ) -> Dict[str, Any]:
        logger.info(f"Query recue: {query}")
        logger.info(f"Mode: {mode}")
        logger.info(f"Sources: {sources}")

        cleaned_query = self._clean_query(query)
        if not cleaned_query:
            return self._empty_response("La requete est vide apres nettoyage.")

        try:
            plan = self.router.build_plan(
                query=cleaned_query,
                mode=mode,
                requested_sources=sources,
            )
            plan["intent_hint"] = self.router.detect_intent(cleaned_query, self.llm)
            logger.info(f"Plan genere: {plan}")
        except ValueError as exc:
            logger.exception("Erreur lors de la construction du plan")
            return self._error_response(str(exc), sources=sources)

        pipeline = self._build_pipeline(plan["strategy"])
        result = pipeline.run(
            query=plan["query"],
            sources=plan["sources"],
            raw_results=raw_results,
        )
        result["mode"] = plan["mode"]
        result["strategy"] = plan["strategy"]
        result["tools_used"] = plan["tools"]
        result["intent_hint"] = plan["intent_hint"]
        return result

    def _build_pipeline(self, strategy: str) -> SearchPipeline | IncidentPipeline:
        if strategy == "search_pipeline":
            return SearchPipeline(self.tools, self.llm)
        if strategy == "incident_pipeline":
            return IncidentPipeline(self.tools, self.llm)
        raise ValueError(f"Strategie inconnue: {strategy}")

    @staticmethod
    def _clean_query(query: str) -> str:
        return " ".join(query.split()).strip()

    @staticmethod
    def _empty_response(message: str) -> Dict[str, Any]:
        return {
            "summary": message,
            "data": [],
            "issues": ["Requete vide"],
            "analysis": "Aucune execution effectuee.",
            "sources": [],
            "raw_results": [],
            "job_offers": [],
            "report_files": {},
            "mode": None,
            "strategy": None,
            "tools_used": [],
            "intent_hint": None,
        }

    @staticmethod
    def _error_response(message: str, sources: List[str] | None = None) -> Dict[str, Any]:
        return {
            "summary": "Erreur de routage",
            "data": [],
            "issues": [message],
            "analysis": "Le routeur n'a pas pu construire un plan valide.",
            "sources": sources or [],
            "raw_results": [],
            "job_offers": [],
            "report_files": {},
            "mode": None,
            "strategy": None,
            "tools_used": [],
            "intent_hint": None,
        }


def run_agent(query: str, mode: str, sources: List[str]) -> Dict[str, Any]:
    orchestrator = AgentOrchestrator()
    return orchestrator.run(query=query, mode=mode, sources=sources)


def run_agent_with_prefetched_results(
    query: str,
    mode: str,
    sources: List[str],
    raw_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    orchestrator = AgentOrchestrator()
    return orchestrator.run_with_prefetched_results(
        query=query,
        mode=mode,
        sources=sources,
        raw_results=raw_results,
    )
