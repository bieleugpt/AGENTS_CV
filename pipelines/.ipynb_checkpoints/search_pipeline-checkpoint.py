


#AXA_IA/__axa/agent_cv/pipelines/search_pipeline.py

from typing import Dict, Any, List

from llm.ollama_client import OllamaClient


class SearchPipeline:
    def __init__(self, tools: Dict[str, Any], llm: OllamaClient):
        self.tools = tools
        self.llm = llm

    def run(self, query: str, sources: List[str]) -> Dict[str, Any]:
        raw_results = self._collect_data(query, sources)

        structured = self.llm.structured_analysis(
            raw_data=str(raw_results),
            query=query
        )

        pipeline_issues = self._extract_pipeline_issues(raw_results)
        llm_issues = structured.get("issues", [])

        return {
            "summary": structured.get("summary"),
            "data": structured.get("data"),
            "issues": pipeline_issues + llm_issues,
            "analysis": structured.get("analysis"),
            "sources": sources,
        }

    def _collect_data(self, query: str, sources: List[str]) -> List[Dict[str, Any]]:
        results = []

        for source in sources:
            if source.startswith("http") or source.lower() in ["site_a", "site_b", "booking"] or "site" in source.lower():
                content = self.tools["web"].search(query, source)
            elif "sql" in source.lower():
                content = self.tools["sql"].query(query)
            else:
                content = f"[WARNING] Source non supportée: {source}"

            status = "success"
            if "[ERROR]" in content or "[PLAYWRIGHT ERROR]" in content or "[WARNING]" in content:
                status = "error"

            results.append({
                "source": source,
                "status": status,
                "content": content
            })

        return results

    def _extract_pipeline_issues(self, raw_results: List[Dict[str, Any]]) -> List[str]:
        issues = []

        for item in raw_results:
            if item["status"] != "success":
                issues.append(f"Problème sur la source {item['source']}")

        if not issues:
            issues.append("Aucune anomalie technique détectée")

        return issues









    