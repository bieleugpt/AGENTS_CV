from __future__ import annotations

import csv
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


REPORTS_DIR = Path(__file__).resolve().parents[1] / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class JobOffer:
    source: str
    title: str
    company: str
    location: str
    contract: str
    salary: str
    snippet: str
    search_url: str
    score: int


def build_job_search_result(query: str, raw_results: list[dict[str, Any]]) -> dict[str, Any] | None:
    offers = extract_job_offers(query=query, raw_results=raw_results)
    if not offers:
        return None

    report_files = write_reports(query=query, offers=offers)
    top_offers = [asdict(offer) for offer in offers[:10]]

    return {
        "summary": (
            f"{len(offers)} offres detectees et classees automatiquement. "
            f"Rapport genere: {report_files['markdown']}"
        ),
        "data": {
            "top_offers": top_offers,
            "report_markdown": report_files["markdown"],
            "report_csv": report_files["csv"],
        },
        "analysis": (
            "Classement automatique base sur les mots-cles de la requete, "
            "la presence d'un contrat, d'une localisation et d'un salaire."
        ),
        "job_offers": top_offers,
        "report_files": report_files,
    }


def extract_job_offers(query: str, raw_results: list[dict[str, Any]]) -> list[JobOffer]:
    offers: list[JobOffer] = []
    for item in raw_results:
        if item.get("status") != "success":
            continue
        if item.get("source") == "hellowork_jobs":
            offers.extend(
                parse_hellowork_offers(
                    query=query,
                    content=str(item.get("content", "")),
                    source=str(item.get("source", "")),
                )
            )
    return sorted(offers, key=lambda offer: offer.score, reverse=True)


def parse_hellowork_offers(query: str, content: str, source: str) -> list[JobOffer]:
    if "Voir l’offre" not in content and "Voir l'offre" not in content:
        return []

    query_tokens = _query_tokens(query)
    search_url = _extract_search_url(content)
    blocks = re.split(r"Voir l[’']offre", content)
    offers: list[JobOffer] = []

    for block in blocks:
        lines = _clean_lines(block)
        if len(lines) < 4:
            continue

        title_index = _find_title_index(lines)
        if title_index is None:
            continue

        title = lines[title_index]
        company = _pick_company(lines, title_index)
        location = _pick_location(lines, title_index)
        contract = _pick_contract(lines, title_index)
        salary = _pick_salary(lines, title_index)
        snippet = _pick_snippet(lines, title_index)

        offers.append(
            JobOffer(
                source=source,
                title=title,
                company=company,
                location=location,
                contract=contract,
                salary=salary,
                snippet=snippet,
                search_url=search_url,
                score=_score_offer(
                    title=title,
                    company=company,
                    location=location,
                    contract=contract,
                    salary=salary,
                    snippet=snippet,
                    query_tokens=query_tokens,
                ),
            )
        )

    deduped: dict[tuple[str, str, str], JobOffer] = {}
    for offer in offers:
        key = (offer.title.lower(), offer.company.lower(), offer.location.lower())
        previous = deduped.get(key)
        if previous is None or offer.score > previous.score:
            deduped[key] = offer

    return list(deduped.values())


def write_reports(query: str, offers: list[JobOffer]) -> dict[str, str]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = _slugify(query)[:60] or "job_search"
    markdown_path = REPORTS_DIR / f"{timestamp}_{slug}.md"
    csv_path = REPORTS_DIR / f"{timestamp}_{slug}.csv"

    markdown_path.write_text(_build_markdown_report(query, offers), encoding="utf-8")
    _write_csv_report(csv_path, offers)

    return {
        "markdown": str(markdown_path),
        "csv": str(csv_path),
    }


def _build_markdown_report(query: str, offers: list[JobOffer]) -> str:
    lines = [
        "# Rapport offres emploi",
        "",
        f"Requete: {query}",
        f"Nombre d'offres classees: {len(offers)}",
        "",
        "| Score | Titre | Entreprise | Localisation | Contrat | Salaire | Source |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]

    for offer in offers:
        lines.append(
            f"| {offer.score} | {_md(offer.title)} | {_md(offer.company)} | "
            f"{_md(offer.location)} | {_md(offer.contract)} | {_md(offer.salary)} | "
            f"{_md(offer.search_url)} |"
        )

    lines.extend(["", "## Details", ""])
    for index, offer in enumerate(offers, start=1):
        lines.extend(
            [
                f"### {index}. {offer.title}",
                f"- Entreprise: {offer.company}",
                f"- Localisation: {offer.location}",
                f"- Contrat: {offer.contract}",
                f"- Salaire: {offer.salary}",
                f"- Score: {offer.score}",
                f"- URL de recherche: {offer.search_url}",
                f"- Extrait: {offer.snippet}",
                "",
            ]
        )

    return "\n".join(lines)


def _write_csv_report(path: Path, offers: list[JobOffer]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "score",
                "title",
                "company",
                "location",
                "contract",
                "salary",
                "snippet",
                "search_url",
                "source",
            ],
        )
        writer.writeheader()
        for offer in offers:
            writer.writerow(asdict(offer))


def _extract_search_url(content: str) -> str:
    match = re.search(r"URL FINALE:\s*(https?://\S+)", content)
    return match.group(1) if match else ""


def _clean_lines(block: str) -> list[str]:
    lines = [line.strip(" -\t") for line in block.splitlines() if line.strip()]
    return [line for line in lines if line not in {"Input", "Filtres", "Rechercher"}]


def _find_title_index(lines: list[str]) -> int | None:
    for index, line in enumerate(lines):
        normalized = line.lower()
        if normalized.startswith(("source:", "url finale:", "titre page:", "contenu:")):
            continue
        if " h/f" in normalized or "f/h" in normalized:
            return index
    for index, line in enumerate(lines):
        if len(line) > 12 and not _looks_like_metadata(line):
            return index
    return None


def _pick_company(lines: list[str], title_index: int) -> str:
    for line in lines[title_index + 1:title_index + 5]:
        if not _looks_like_metadata(line):
            return line
    return ""


def _pick_location(lines: list[str], title_index: int) -> str:
    for line in lines[title_index + 1:title_index + 8]:
        if re.search(r"\b\d{2,5}\b", line) or " - " in line:
            return line
    return ""


def _pick_contract(lines: list[str], title_index: int) -> str:
    for line in lines[title_index:title_index + 8]:
        if any(token in line.lower() for token in ["cdi", "cdd", "alternance", "stage", "interim", "freelance"]):
            return line
    return ""


def _pick_salary(lines: list[str], title_index: int) -> str:
    for line in lines[title_index:title_index + 10]:
        if "€" in line or "euro" in line.lower():
            return line
    return ""


def _pick_snippet(lines: list[str], title_index: int) -> str:
    for line in lines[title_index + 1:title_index + 12]:
        if not _looks_like_metadata(line) and len(line) > 40:
            return line
    return ""


def _score_offer(
    title: str,
    company: str,
    location: str,
    contract: str,
    salary: str,
    snippet: str,
    query_tokens: set[str],
) -> int:
    text = " ".join([title, company, location, contract, salary, snippet]).lower()
    score = sum(5 for token in query_tokens if token in text)
    if contract:
        score += 2
    if location:
        score += 2
    if salary:
        score += 1
    if snippet:
        score += 2
    return score


def _query_tokens(query: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z0-9+#]{3,}", query.lower())
        if token not in {"avec", "dans", "pour", "des", "les", "une", "que"}
    }


def _looks_like_metadata(line: str) -> bool:
    lower = line.lower()
    if lower in {"super recruteur", "voir l’offre", "voir l'offre"}:
        return True
    if lower.startswith("il y a "):
        return True
    if "offres d'emploi" in lower or lower.startswith("emploi "):
        return True
    return False


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _md(value: str) -> str:
    return value.replace("|", "\\|")
