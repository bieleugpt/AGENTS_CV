from typing import Any, Dict, List

from llm.ollama_client import OllamaClient
from pipelines.source_executor import detect_content_issue, execute_source_query


class IncidentPipeline:
    def __init__(self, tools: Dict[str, Any], llm: OllamaClient):
        self.tools = tools
        self.llm = llm

    def run(
        self,
        query: str,
        sources: List[str],
        raw_results: List[Dict[str, Any]] | None = None,
    ) -> Dict[str, Any]:
        incidents = raw_results or self._collect_incidents(query, sources)
        issues = self._detect_issues(incidents)
        blocking_issue = self._find_blocking_issue(incidents)

        if blocking_issue:
            structured = self._build_blocked_response()
        else:
            structured = self.llm.structured_analysis(
                raw_data=str(incidents),
                query=query,
            )

        return {
            "summary": self._build_summary(incidents, structured, blocking_issue),
            "data": structured.get("data"),
            "issues": issues + structured.get("issues", []),
            "analysis": structured.get("analysis"),
            "sources": sources,
            "raw_results": incidents,
        }

    def _collect_incidents(self, query: str, sources: List[str]) -> List[Dict[str, Any]]:
        results = []

        for source in sources:
            source_result = execute_source_query(query, source, self.tools)
            results.append({
                "source": source_result["source"],
                "source_kind": source_result["source_kind"],
                "status": source_result["status"],
                "incident_data": source_result["content"],
            })

        return results

    def _detect_issues(self, incidents: List[Dict[str, Any]]) -> List[str]:
        issues = []

        for item in incidents:
            content = str(item.get("incident_data", ""))
            specific_issue = detect_content_issue(content)

            if specific_issue:
                issues.append(f"{specific_issue} sur la source {item['source']}")
                continue

            if "error" in content.lower() or "warning" in content.lower():
                issues.append(f"Erreur detectee dans {item['source']}")

        if not issues:
            issues.append("Aucune anomalie detectee")

        return issues

    def _build_summary(
        self,
        incidents: List[Dict[str, Any]],
        structured: Dict[str, Any],
        blocking_issue: str | None,
    ) -> str:
        if blocking_issue:
            for item in incidents:
                specific_issue = detect_content_issue(str(item.get("incident_data", "")))
                if specific_issue:
                    return f"Collecte impossible: {specific_issue.lower()} sur {item['source']}."

        return structured.get("summary")

    def _find_blocking_issue(self, incidents: List[Dict[str, Any]]) -> str | None:
        for item in incidents:
            specific_issue = detect_content_issue(str(item.get("incident_data", "")))
            if specific_issue:
                return specific_issue
        return None

    @staticmethod
    def _build_blocked_response() -> Dict[str, Any]:
        return {
            "summary": "",
            "data": "Aucune donnee exploitable: page anti-bot ou JavaScript requis",
            "issues": [],
            "analysis": "La source a retourne une page de verification anti-bot. Le contenu metier n'a pas pu etre collecte.",
        }
