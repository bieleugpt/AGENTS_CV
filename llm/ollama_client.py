import json
import os
from typing import Any, Dict

import requests

from llm.prompts import (
    build_intent_prompt,
    build_structured_prompt,
    build_summary_prompt,
)

OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")


class OllamaClient:
    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model

    def generate(self, prompt: str, temperature: float = 0.2) -> str:
        """Appel standard a Ollama."""
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
        except requests.exceptions.HTTPError as exc:
            response_text = ""
            if exc.response is not None:
                response_text = exc.response.text[:300]
            return (
                f"[OLLAMA ERROR] HTTP {exc.response.status_code if exc.response else 'unknown'} "
                f"sur le modele '{self.model}'. {response_text}"
            ).strip()
        except requests.exceptions.RequestException as exc:
            return f"[OLLAMA ERROR] {str(exc)}"

    def analyze(self, query: str) -> str:
        prompt = build_intent_prompt(query)
        return self.generate(prompt)

    def summarize(self, raw_data: str, query: str) -> str:
        prompt = build_summary_prompt(raw_data, query)
        return self.generate(prompt)

    def structured_analysis(self, raw_data: str, query: str) -> Dict[str, Any]:
        prompt = build_structured_prompt(raw_data, query)
        output = self.generate(prompt)

        if output.startswith("[OLLAMA ERROR]"):
            return {
                "summary": "Analyse LLM indisponible",
                "data": raw_data[:500],
                "issues": [output],
                "analysis": "Le service Ollama n'a pas retourne de reponse exploitable.",
            }

        json_payload = self._extract_json_payload(output)
        try:
            parsed = json.loads(json_payload)
            return {
                "summary": parsed.get("summary", ""),
                "data": parsed.get("data", ""),
                "issues": parsed.get("issues", []),
                "analysis": parsed.get("analysis", ""),
            }
        except Exception:
            return {
                "summary": "Erreur parsing JSON",
                "data": raw_data[:500],
                "issues": ["Parsing JSON echoue"],
                "analysis": output,
            }

    @staticmethod
    def _extract_json_payload(output: str) -> str:
        start = output.find("{")
        end = output.rfind("}")

        if start == -1:
            return output

        if end == -1 or end < start:
            return output[start:] + "}"

        return output[start:end + 1]
