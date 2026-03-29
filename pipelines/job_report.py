from __future__ import annotations

import csv
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


REPORTS_DIR = Path(__file__).resolve().parents[1] / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

CONTRACT_KEYWORDS = {
    "cdi": "CDI",
    "cdd": "CDD",
    "alternance": "Alternance",
    "stage": "Stage",
    "interim": "Interim",
    "freelance": "Freelance",
}


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
    top_offers = [asdict(offer) for offer in offers[:25]]

    return {
        "summary": (
            f"{len(offers)} offres detectees et classees automatiquement. "
            f"Rapport genere: {report_files['markdown']}"
        ),
        "data": {
            "top_offers": top_offers[:10],
            "report_markdown": report_files["markdown"],
            "report_csv": report_files["csv"],
        },
        "analysis": (
            "Classement automatique base sur la correspondance des mots-cles, "
            "la presence d'un contrat, d'une localisation, d'un salaire et d'un extrait exploitable."
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
    if "serpCard" not in content and "Voir l" not in content:
        return []

    query_tokens = _query_tokens(query)
    search_url = _extract_search_url(content)
    offers: list[JobOffer] = []

    blocks = _split_hellowork_blocks(content)

    for block in blocks:
        offer = _parse_hellowork_block(
            lines=_clean_lines(block),
            source=source,
            search_url=search_url,
            query_tokens=query_tokens,
        )
        if offer:
            offers.append(offer)

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
    lines = []
    for raw_line in block.splitlines():
        line = raw_line.strip(" -\t")
        if not line:
            continue
        if line in {"Input", "Filtres", "Rechercher"}:
            continue
        if line.startswith("http"):
            continue
        if line in {">", '>"'}:
            continue
        lines.append(line)
    return lines


def _split_hellowork_blocks(content: str) -> list[str]:
    card_blocks = re.split(r'data-cy="serpCard"', content)
    if len(card_blocks) > 1:
        return card_blocks[1:]
    return re.split(r"Voir l[â€™' ]offre", content)


def _parse_hellowork_block(
    lines: list[str],
    source: str,
    search_url: str,
    query_tokens: set[str],
) -> JobOffer | None:
    if len(lines) < 4:
        return None

    title_index = _find_title_index(lines)
    if title_index is None:
        return None

    title = lines[title_index]
    company = _pick_company(lines, title_index)
    location = _pick_location(lines, title_index)
    contract = _pick_contract(lines, title_index)
    salary = _pick_salary(lines, title_index)
    snippet = _pick_snippet(lines, title_index, title, company, location, contract, salary)

    if not title or not company:
        return None

    return JobOffer(
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


def _find_title_index(lines: list[str]) -> int | None:
    for index, line in enumerate(lines):
        normalized = line.lower()
        if normalized.startswith(("source:", "url finale:", "titre page:", "contenu:")):
            continue
        if _looks_like_salary(line) or _looks_like_location(line) or _looks_like_metadata(line):
            continue
        if " h/f" in normalized or "f/h" in normalized:
            return index

    for index, line in enumerate(lines):
        if len(line) > 12 and not (_looks_like_metadata(line) or _looks_like_salary(line) or _looks_like_location(line)):
            return index
    return None


def _pick_company(lines: list[str], title_index: int) -> str:
    for line in lines[title_index + 1:title_index + 6]:
        if _looks_like_metadata(line) or _looks_like_salary(line) or _looks_like_location(line) or _looks_like_contract(line):
            continue
        return line
    return ""


def _pick_location(lines: list[str], title_index: int) -> str:
    for line in lines[title_index + 1:title_index + 8]:
        if _looks_like_salary(line):
            continue
        if _looks_like_location(line):
            return line
    return ""


def _pick_contract(lines: list[str], title_index: int) -> str:
    for line in lines[title_index:title_index + 8]:
        contract = _normalize_contract(line)
        if contract:
            return contract
    return ""


def _pick_salary(lines: list[str], title_index: int) -> str:
    for line in lines[title_index:title_index + 10]:
        if _looks_like_salary(line):
            return line
    return ""


def _pick_snippet(
    lines: list[str],
    title_index: int,
    title: str,
    company: str,
    location: str,
    contract: str,
    salary: str,
) -> str:
    excluded = {title, company, location, contract, salary, ""}
    for line in lines[title_index + 1:title_index + 14]:
        if line in excluded:
            continue
        if _looks_like_metadata(line) or _looks_like_salary(line) or _looks_like_location(line):
            continue
        if line.lower().startswith("télétravail") or line.lower().startswith("teletravail"):
            return line
        if line.lower().startswith("début le") or line.lower().startswith("debut le"):
            return line
        if len(line) >= 20:
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
    score = 0

    for token in query_tokens:
        if token in text:
            score += 5

    positive_tokens = {"python", "fullstack", "backend", "frontend", "remote", "sql", "java", "react"}
    negative_tokens = {"stagiaire", "intern", "benevole"}

    for token in positive_tokens:
        if token in query_tokens and token in text:
            score += 3

    for token in negative_tokens:
        if token in text and token not in query_tokens:
            score -= 4

    if contract:
        score += 2
    if location:
        score += 2
    if salary:
        score += 2
    if snippet:
        score += 3
    if company:
        score += 1

    return score


def _query_tokens(query: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z0-9+#]{3,}", query.lower())
        if token not in {"avec", "dans", "pour", "des", "les", "une", "que"}
    }


def _normalize_contract(line: str) -> str:
    lower = line.lower()
    for token, label in CONTRACT_KEYWORDS.items():
        if token in lower:
            return label
    return ""


def _looks_like_contract(line: str) -> bool:
    return bool(_normalize_contract(line))


def _looks_like_salary(line: str) -> bool:
    lower = line.lower()
    return "€" in line or "â‚¬" in line or "euro" in lower or "/ an" in lower or "/ mois" in lower


def _looks_like_location(line: str) -> bool:
    if _looks_like_salary(line):
        return False
    if re.search(r"\b\d{2,5}\b", line):
        return True
    if " - " in line:
        return True
    return False


def _looks_like_metadata(line: str) -> bool:
    lower = line.lower()
    if lower in {"super recruteur", "voir lâ€™offre", "voir l'offre", "voir l’offre"}:
        return True
    if lower.startswith("il y a "):
        return True
    if "offres d'emploi" in lower or lower.startswith("emploi "):
        return True
    if lower.startswith(("source:", "url finale:", "titre page:", "contenu:")):
        return True
    if any(token in lower for token in [
        'analytics#push',
        'data-cy=',
        'toggle#',
        'input-checker#',
        'details#',
        'autocomplete#',
        'append-values#',
        'class="',
        'data-controller=',
    ]):
        return True
    return False


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _md(value: str) -> str:
    return value.replace("|", "\\|")
