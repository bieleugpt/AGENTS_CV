


#AXA_IA/__axa/agent_cv/llm/ollama_client.py

import requests
from typing import Dict, Any

from llm.ollama_client import OllamaClient
import json


OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "llama3"


class OllamaClient:
    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model

    def generate(self, prompt: str, temperature: float = 0.2) -> str:
        """
        Appel simple à Ollama (non streaming)
        """
        try:
            response = requests.post(
                OLLAMA_URL,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "temperature": temperature,
                    "stream": False,
                },
                timeout=60,
            )

            response.raise_for_status()
            data = response.json()

            return data.get("response", "").strip()

        except requests.exceptions.RequestException as e:
            return f"[OLLAMA ERROR] {str(e)}"

    def analyze(self, query: str) -> str:
        """
        Compréhension de la requête utilisateur
        """
        from llm.prompts import build_intent_prompt

        prompt = build_intent_prompt(query)
        return self.generate(prompt)

    def summarize(self, raw_data: str, query: str) -> str:
        """
        Résumé structuré des résultats
        """
        from llm.prompts import build_summary_prompt

        prompt = build_summary_prompt(raw_data, query)
        return self.generate(prompt)

    def structured_analysis(self, raw_data: str, query: str) -> Dict[str, Any]:
        """
        Analyse avancée (format JSON attendu)
        """
        from llm.prompts import build_structured_prompt
        import json

        prompt = build_structured_prompt(raw_data, query)
        output = self.generate(prompt)

        try:
            return json.loads(output)
        except Exception:
            return {
                "summary": "Erreur parsing JSON",
                "analysis": output,
                "issues": ["Parsing échoué"],
            }