def build_intent_prompt(query: str) -> str:
    return f"""
Tu classes une requete utilisateur dans une seule categorie.

Categories autorisees :
- incident
- recherche

Regles :
- Reponds avec un seul mot
- Pas de phrase complete
- Si tu hesites, reponds recherche

Requete :
{query}
""".strip()


def build_summary_prompt(raw_data: str, query: str) -> str:
    return f"""
Tu es un analyste factuel.

Question utilisateur :
{query}

Donnees disponibles :
{raw_data}

Fais une synthese concise basee uniquement sur les donnees fournies.
Si les donnees sont insuffisantes, dis-le explicitement.
""".strip()


def build_structured_prompt(raw_data: str, query: str) -> str:
    return f"""
Tu es un analyste data rigoureux.

REGLES OBLIGATOIRES :
- Tu reponds uniquement a partir des donnees fournies
- Tu n'inventes jamais d'information
- Si les donnees sont insuffisantes, tu le dis explicitement
- Tu reponds STRICTEMENT au format JSON valide
- Aucun texte avant ou apres le JSON

Question utilisateur :
{query}

Donnees disponibles :
{raw_data}

Format JSON attendu :
{{
  "summary": "resume factuel base uniquement sur les donnees",
  "data": "donnees utiles extraites ou 'aucune donnee exploitable'",
  "issues": ["liste de problemes detectes"],
  "analysis": "analyse factuelle ou explication de l'impossibilite d'analyser"
}}
""".strip()
