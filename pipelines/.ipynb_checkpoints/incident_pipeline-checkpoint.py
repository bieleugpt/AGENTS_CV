


#AXA_IA/__axa/agent_cv/pipelines/incident_pipeline.py

from typing import Dict, Any, List

from llm.ollama_client import OllamaClient


class IncidentPipeline:
    def __init__(self, tools: Dict[str, Any], llm: OllamaClient):
        self.tools = tools
        self.llm = llm

    def run(self, query: str, sources: List[str]) -> Dict[str, Any]:
        incidents = self._collect_incidents(query, sources)
        issues = self._detect_issues(incidents)

        structured = self.llm.structured_analysis(
            raw_data=str(incidents),
            query=query
        )

        return {
            "summary": structured.get("summary"),
            "data": structured.get("data"),
            "issues": issues + structured.get("issues", []),
            "analysis": structured.get("analysis"),
            "sources": sources,
        }

    def _collect_incidents(self, query: str, sources: List[str]) -> List[Dict[str, Any]]:
        results = []

        for source in sources:
            if source.startswith("http") or source.lower() in ["site_a", "site_b", "booking"] or "site" in source.lower():
                content = self.tools["web"].search(query, source)
            elif "sql" in source.lower():
                content = self.tools["sql"].query(query)
            else:
                content = "[WARNING] Source non supportée"

            results.append({
                "source": source,
                "incident_data": content
            })

        return results

    def _detect_issues(self, incidents: List[Dict[str, Any]]) -> List[str]:
        issues = []

        for item in incidents:
            content = str(item.get("incident_data", ""))

            if "error" in content.lower() or "warning" in content.lower():
                issues.append(f"Erreur détectée dans {item['source']}")

        if not issues:
            issues.append("Aucune anomalie détectée")

        return issues


