


#AXA_IA/__axa/agent_cv/llm/ollama_client.py

import requests
import json
from typing import Dict, Any

from llm.prompts import (
    build_intent_prompt,
    build_summary_prompt,
    build_structured_prompt,
)

OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "llama3"


class OllamaClient:
    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model

    def generate(self, prompt: str, temperature: float = 0.2) -> str:
        """
        Appel standard à Ollama
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

    # =====================================================
    # HIGH LEVEL METHODS
    # =====================================================

    def analyze(self, query: str) -> str:
        prompt = build_intent_prompt(query)
        return self.generate(prompt)

    def summarize(self, raw_data: str, query: str) -> str:
        prompt = build_summary_prompt(raw_data, query)
        return self.generate(prompt)



        
    def structured_analysis(self, raw_data: str, query: str) -> Dict[str, Any]:
        prompt = build_structured_prompt(raw_data, query)
        output = self.generate(prompt)
    
        try:
            parsed = json.loads(output)
    
            # sécurité minimale
            return {
                "summary": parsed.get("summary", ""),
                "data": parsed.get("data", ""),
                "issues": parsed.get("issues", []),
                "analysis": parsed.get("analysis", "")
            }
    
        except Exception:
            return {
                "summary": "Erreur parsing JSON",
                "data": raw_data[:500],
                "issues": ["Parsing JSON échoué"],
                "analysis": output,
            }



