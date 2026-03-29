from typing import Any, Dict, List

from llm.ollama_client import OllamaClient
from pipelines.job_report import build_job_search_result
from pipelines.source_executor import detect_content_issue, execute_source_query


class SearchPipeline:
    def __init__(self, tools: Dict[str, Any], llm: OllamaClient):
        self.tools = tools
        self.llm = llm

    def run(
        self,
        query: str,
        sources: List[str],
        raw_results: List[Dict[str, Any]] | None = None,
    ) -> Dict[str, Any]:
        raw_results = raw_results or self._collect_data(query, sources)
        blocking_issue = self._find_blocking_issue(raw_results)
        job_search_result = build_job_search_result(query=query, raw_results=raw_results)
        has_job_source = any(item.get("source") == "hellowork_jobs" for item in raw_results)

        if job_search_result:
            return {
                "summary": job_search_result["summary"],
                "data": job_search_result["data"],
                "issues": self._extract_pipeline_issues(raw_results),
                "analysis": job_search_result["analysis"],
                "sources": sources,
                "raw_results": raw_results,
                "job_offers": job_search_result["job_offers"],
                "report_files": job_search_result["report_files"],
            }

        if has_job_source:
            return {
                "summary": "Extraction d'offres incomplete",
                "data": "Aucune offre structuree n'a pu etre extraite depuis la page publique.",
                "issues": self._extract_pipeline_issues(raw_results),
                "analysis": (
                    "La source publique a repondu, mais le contenu recupere n'a pas pu etre "
                    "transforme en offres structurees. Le fallback LLM est desactive pour cette source."
                ),
                "sources": sources,
                "raw_results": raw_results,
                "job_offers": [],
                "report_files": {},
            }

        if blocking_issue:
            structured = self._build_blocked_response()
        else:
            structured = self.llm.structured_analysis(
                raw_data=str(raw_results),
                query=query,
            )

        pipeline_issues = self._extract_pipeline_issues(raw_results)
        llm_issues = structured.get("issues", [])

        return {
            "summary": self._build_summary(raw_results, structured, blocking_issue),
            "data": structured.get("data"),
            "issues": pipeline_issues + llm_issues,
            "analysis": structured.get("analysis"),
            "sources": sources,
            "raw_results": raw_results,
            "job_offers": [],
            "report_files": {},
        }

    def _collect_data(self, query: str, sources: List[str]) -> List[Dict[str, Any]]:
        return [
            execute_source_query(query, source, self.tools)
            for source in sources
        ]

    def _extract_pipeline_issues(self, raw_results: List[Dict[str, Any]]) -> List[str]:
        issues = []

        for item in raw_results:
            if item["status"] == "success":
                continue

            specific_issue = detect_content_issue(str(item.get("content", "")))
            if specific_issue:
                issues.append(f"{specific_issue} sur la source {item['source']}")
            else:
                issues.append(f"Probleme sur la source {item['source']}")

        if not issues:
            issues.append("Aucune anomalie technique detectee")

        return issues

    def _build_summary(
        self,
        raw_results: List[Dict[str, Any]],
        structured: Dict[str, Any],
        blocking_issue: str | None,
    ) -> str:
        if blocking_issue:
            for item in raw_results:
                specific_issue = detect_content_issue(str(item.get("content", "")))
                if specific_issue:
                    return f"Collecte impossible: {specific_issue.lower()} sur {item['source']}."

        return structured.get("summary")

    def _find_blocking_issue(self, raw_results: List[Dict[str, Any]]) -> str | None:
        for item in raw_results:
            specific_issue = detect_content_issue(str(item.get("content", "")))
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
