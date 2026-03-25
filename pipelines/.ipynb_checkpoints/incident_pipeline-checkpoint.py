


#AXA_IA/__axa/agent_cv/pipelines/incident_pipeline.py
from typing import Dict, Any, List

from llm.ollama_client import OllamaClient


class IncidentPipeline:
    def __init__(self, tools: Dict[str, Any], llm: OllamaClient):
        self.tools = tools
        self.llm = llm

    def run(self, query: str, sources: List[str]) -> Dict[str, Any]:
        # =====================================================
        # 1. Récupération incidents
        # =====================================================
        incidents = self._collect_incidents(query, sources)

        # =====================================================
        # 2. Détection anomalies simples
        # =====================================================
        issues = self._detect_issues(incidents)

        # =====================================================
        # 3. Analyse LLM
        # =====================================================
        structured = self.llm.structured_analysis(
            raw_data=str(incidents),
            query=query
        )

        # =====================================================
        # 4. Output
        # =====================================================
        return {
            "summary": structured.get("summary"),
            "data": structured.get("data"),
            "issues": issues,
            "analysis": structured.get("analysis"),
            "sources": sources,
        }

    # =========================================================
    # INTERNALS
    # =========================================================

    def _collect_incidents(self, query: str, sources: List[str]) -> List[Dict[str, Any]]:
        results = []

        for source in sources:
            if "sql" in source.lower():
                content = self.tools["sql"].query(query)
            elif "site" in source.lower():
                content = self.tools["web"].search(query, source)
            else:
                content = "Source non supportée"

            results.append({
                "source": source,
                "incident_data": content
            })

        return results

    def _detect_issues(self, incidents: List[Dict[str, Any]]) -> List[str]:
        issues = []

        for item in incidents:
            content = str(item.get("incident_data", ""))

            if "error" in content.lower():
                issues.append(f"Erreur détectée dans {item['source']}")

        if not issues:
            issues.append("Aucune anomalie détectée")

        return issues