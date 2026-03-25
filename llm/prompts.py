

#AXA_IA/__axa/agent_cv/llm/prompts.py

def build_intent_prompt(query: str) -> str:
    return f"""
Analyse la requête utilisateur et reformule clairement son objectif.

Requête:
{query}

Réponse:
""".strip()


def build_summary_prompt(raw_data: str, query: str) -> str:
    return f"""
Tu es un assistant data.

Objectif:
Répondre à la question en utilisant les données.

Question:
{query}

Données:
{raw_data}

Réponse claire et concise:
""".strip()


def build_structured_prompt(raw_data: str, query: str) -> str:
    return f"""
Tu es un assistant d'analyse.

Réponds STRICTEMENT en JSON valide.

Question:
{query}

Données:
{raw_data}

Format:
{{
  "summary": "résumé court",
  "data": "infos utiles",
  "issues": ["Aucune anomalie"],
  "analysis": "explication claire"
}}

JSON:
""".strip()







