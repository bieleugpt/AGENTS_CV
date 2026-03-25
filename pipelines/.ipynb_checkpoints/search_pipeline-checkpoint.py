


#AXA_IA/__axa/agent_cv/pipelines/search_pipeline.py
from typing import Dict, Any, List

from llm.ollama_client import OllamaClient


class SearchPipeline:
    def __init__(self, tools: Dict[str, Any], llm: OllamaClient):
        self.tools = tools
        self.llm = llm

    def run(self, query: str, sources: List[str]) -> Dict[str, Any]:
        # =====================================================
        # 1. Récupération des données
        # =====================================================
        raw_results = self._collect_data(query, sources)

        # =====================================================
        # 2. Analyse LLM (structurée)
        # =====================================================
        structured = self.llm.structured_analysis(
            raw_data=str(raw_results),
            query=query
        )

        # =====================================================
        # 3. Output standardisé
        # =====================================================
        return {
            "summary": structured.get("summary"),
            "data": structured.get("data"),
            "issues": structured.get("issues"),
            "analysis": structured.get("analysis"),
            "sources": sources,
        }

    # =========================================================
    # INTERNALS
    # =========================================================

    def _collect_data(self, query: str, sources: List[str]) -> List[Dict[str, Any]]:
        results = []

        for source in sources:
            if "site" in source.lower():
                content = self.tools["web"].search(query, source)
            elif "sql" in source.lower():
                content = self.tools["sql"].query(query)
            else:
                content = f"Source non gérée: {source}"

            results.append({
                "source": source,
                "content": content
            })

        return results