

#AXA_IA/__axa/agent_cv/llm/prompts.py

def build_structured_prompt(raw_data: str, query: str) -> str:
    return f"""
Tu es un analyste data rigoureux.

RÈGLES OBLIGATOIRES :
- Tu réponds uniquement à partir des données fournies
- Tu n'inventes jamais d'information
- Si les données sont insuffisantes, tu le dis explicitement
- Tu réponds STRICTEMENT au format JSON valide
- Aucun texte avant ou après le JSON

Question utilisateur :
{query}

Données disponibles :
{raw_data}

Format JSON attendu :
{{
  "summary": "résumé factuel basé uniquement sur les données",
  "data": "données utiles extraites ou 'aucune donnée exploitable'",
  "issues": ["liste de problèmes détectés"],
  "analysis": "analyse factuelle ou explication de l'impossibilité d'analyser"
}}
""".strip()

    



