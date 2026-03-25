

#AXA_IA/__axa/agent_cv/agent/orchestrator.py

from __future__ import annotations

from typing import List, Dict, Any

from agent.router import Router

from pipelines.search_pipeline import SearchPipeline
from pipelines.incident_pipeline import IncidentPipeline
from llm.ollama_client import OllamaClient




from tools.web.playwright_tool import PlaywrightTool


class AgentOrchestrator:
    """
    Orchestrateur principal.

    Responsabilités :
    - recevoir la demande
    - demander au router un plan d'exécution
    - exécuter une logique simple selon la stratégie
    - retourner une réponse structurée
    """

    def __init__(self, available_sources: List[str] | None = None) -> None:
        self.router = Router(available_sources=available_sources or [])

    def run(self, query: str, mode: str, sources: List[str]) -> Dict[str, Any]:
        """
        Point d'entrée principal de l'agent.
        """
        cleaned_query = self._clean_query(query)

        if not cleaned_query:
            return self._empty_response(
                message="La requête est vide après nettoyage."
            )

        try:
            plan = self.router.build_plan(
                query=cleaned_query,
                mode=mode,
                requested_sources=sources,
            )
        except ValueError as exc:
            return self._error_response(str(exc), sources=sources)

        if plan["strategy"] == "incident_pipeline":
            return self._run_incident_pipeline(plan)


        if plan["strategy"] == "search_pipeline":
            pipeline = SearchPipeline(self.tools, self.llm)
        else:
            pipeline = IncidentPipeline(self.tools, self.llm)
        
        return pipeline.run(
            query=plan["query"],
            sources=plan["sources"]
        )

        
        return self._run_search_pipeline(plan)

    '''
    def _run_search_pipeline(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Pipeline simple de recherche.
        Ici, on simule encore les appels réels.
        """
        extracted_data = self._simulate_tool_execution(plan)

        return {
            "summary": f"Recherche exécutée pour : {plan['query']}",
            "data": extracted_data,
            "issues": self._detect_issues(extracted_data),
            "analysis": self._build_analysis(plan, extracted_data),
            "sources": plan["sources"],
            "mode": plan["mode"],
            "strategy": plan["strategy"],
            "tools_used": plan["tools"],
        }
    '''



    def _run_search_pipeline(self, plan):
        raw_data = self._simulate_tool_execution(plan)
    
        structured = self.llm.structured_analysis(
            raw_data=str(raw_data),
            query=plan["query"]
        )
    
        return {
            "summary": structured.get("summary"),
            "data": structured.get("data"),
            "issues": structured.get("issues"),
            "analysis": structured.get("analysis"),
            "sources": plan["sources"],
        }

    

    def _run_incident_pipeline(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        extracted_data = self._simulate_tool_execution(plan)
    
        ollama = OllamaClient()
    
        raw_data_str = json.dumps(extracted_data, indent=2)
    
        llm_result = ollama.structured_analysis(
            raw_data=raw_data_str,
            query=plan["query"]
        )
    
        return {
            "summary": llm_result.get("summary"),
            "data": llm_result.get("data"),
            "issues": llm_result.get("issues"),
            "analysis": llm_result.get("analysis"),
            "sources": plan["sources"],
            "mode": plan["mode"],
            "strategy": plan["strategy"],
            "tools_used": plan["tools"],
        }

    def _simulate_tool_execution(self, plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Simulation temporaire.
        À remplacer ensuite par de vrais appels :
        - Playwright
        - SQL
        - file parser
        - Ollama
        """
        results: List[Dict[str, Any]] = []

        for source in plan["sources"]:
            results.append({
                "source": source,
                "query": plan["query"],
                "status": "success",
                "content": f"Contenu simulé récupéré depuis {source}",
            })

        if not results:
            results.append({
                "source": "none",
                "query": plan["query"],
                "status": "warning",
                "content": "Aucune source valide fournie.",
            })

        return results

    def _detect_issues(self, data: List[Dict[str, Any]]) -> List[str]:
        """
        Détection simple d'éventuels problèmes.
        """
        issues: List[str] = []

        for item in data:
            if item.get("status") != "success":
                issues.append(
                    f"Problème détecté sur la source {item.get('source', 'unknown')}"
                )

        if not issues:
            issues.append("Aucune anomalie détectée.")

        return issues

    '''
    def _build_analysis(self, plan: Dict[str, Any], data: List[Dict[str, Any]]) -> str:
        """
        Construction d'une analyse simple.
        Cette méthode pourra plus tard appeler Ollama.
        """
        source_count = len(plan["sources"])
        tool_count = len(plan["tools"])
        result_count = len(data)

        return (
            f"La requête a été traitée en mode '{plan['mode']}' "
            f"avec {source_count} source(s), {tool_count} tool(s) "
            f"et {result_count} résultat(s) exploitable(s)."
        )
    '''

    
    def _build_analysis(self, plan, data):
        raw_data = str(data)
    
        return self.llm.summarize(
            raw_data=raw_data,
            query=plan["query"]
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
    """
    Fonction utilitaire compatible avec ton UI actuelle.
    """
    orchestrator = AgentOrchestrator()
    return orchestrator.run(query=query, mode=mode, sources=sources)