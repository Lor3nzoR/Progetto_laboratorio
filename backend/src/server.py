from abc import ABC, abstractmethod
from urllib.parse import urlparse
import asyncio
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.content_filter_strategy import PruningContentFilter
import re
import json
import os
from pathlib import Path
from utilities.parserWikipedia import ParserWikipedia
from utilities.parserGeneric import ParserGeneric
from utilities.evaluation import evaluate_all
from functools import lru_cache
from statistics import mean
from typing import Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# ===== INIZIO MODIFICHE IVAN =====
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DOMAINS_FILE = PROJECT_ROOT / "domains.json"
GS_DIRECTORY = PROJECT_ROOT / "gs_data"


class ParsedDocumentResponse(BaseModel):
    url: str
    domain: str
    title: str
    html_text: str
    parsed_text: str


class GoldStandardEntryResponse(BaseModel):
    url: str
    domain: str
    title: str
    html_text: str
    gold_text: str


class DomainsResponse(BaseModel):
    domains: list[str]


class FullGoldStandardResponse(BaseModel):
    gold_standard: list[GoldStandardEntryResponse]


class EvaluationRequest(BaseModel):
    parsed_text: str = Field(default="", description="Testo parsato in markdown.")
    gold_text: str = Field(default="", description="Testo gold senza markdown.")


class ParseFromHtmlRequest(BaseModel):
    url: str = Field(description="URL usato per selezionare il parser corretto.")
    html_text: str = Field(description="HTML grezzo da parsare direttamente.")


class MetricTriple(BaseModel):
    precision: float
    recall: float
    f1: float


class EvaluationResponse(BaseModel):
    token_level_eval: MetricTriple
    x_eval: dict[str, float]


app = FastAPI(
    title="Web Parsing Backend",
    description="Backend REST per parsing, gold standard ed evaluation.",
    version="1.0.0"
)


@lru_cache(maxsize=1)
def load_assigned_domains() -> list[str]:
    """
    Legge una sola volta domains.json e restituisce la lista dei domini assegnati.
    """
    if not DOMAINS_FILE.exists():
        return []

    content = json.loads(DOMAINS_FILE.read_text(encoding="utf-8"))
    assigned_domains = []

    for item in content.get("domini_assegnati", []):
        domain = str(item.get("domain", "")).strip().lower()
        if domain:
            assigned_domains.append(domain)

    return assigned_domains


def match_assigned_domain(host_or_domain: str) -> str | None:
    """
    Mappa un host reale al dominio assegnato, accettando anche eventuali
    sottodomini come www.* oppure it.*.
    """
    normalized_host = host_or_domain.strip().lower()

    for assigned_domain in load_assigned_domains():
        if normalized_host == assigned_domain:
            return assigned_domain
        if normalized_host.endswith(f".{assigned_domain}"):
            return assigned_domain

    return None


def normalize_url_and_domain(url: str) -> tuple[str, str]:
    """
    Valida l'URL in input e restituisce l'URL pulito insieme al dominio assegnato.
    """
    normalized_url = url.strip()
    parsed_url = urlparse(normalized_url)

    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise HTTPException(
            status_code=400,
            detail="URL non valido. Usare un URL HTTP o HTTPS."
        )

    assigned_domain = match_assigned_domain(parsed_url.netloc)
    if assigned_domain is None:
        raise HTTPException(
            status_code=400,
            detail="Dominio non supportato."
        )

    return normalized_url, assigned_domain


def get_parser_class(domain: str):
    """
    Se disponibile usa il parser dedicato, altrimenti un parser generico di
    fallback per i domini assegnati.
    """
    specific_parsers = {
        "it.wikipedia.org": ParserWikipedia
    }
    return specific_parsers.get(domain, ParserGeneric)


def get_gs_file_path(domain: str) -> Path:
    """
    Costruisce il path del file GS a partire dal nome del dominio assegnato.
    """
    return GS_DIRECTORY / f"{domain.replace('.', '_')}_gs.json"


def load_gold_standard_entries(domain: str) -> list[dict[str, Any]]:
    """
    Legge il Gold Standard del dominio richiesto.
    """
    gs_file = get_gs_file_path(domain)

    if not gs_file.exists():
        raise HTTPException(
            status_code=404,
            detail="Gold Standard non disponibile per il dominio richiesto."
        )

    content = json.loads(gs_file.read_text(encoding="utf-8"))
    if isinstance(content, dict):
        return [content]
    return content


def find_gold_standard_entry(url: str, domain: str) -> dict[str, Any]:
    """
    Recupera l'entry del Gold Standard corrispondente all'URL richiesto.
    """
    for entry in load_gold_standard_entries(domain):
        if entry.get("url") == url:
            return entry

    raise HTTPException(
        status_code=404,
        detail="L'URL richiesto non è presente nel Gold Standard."
    )


async def run_parser(
    url: str,
    domain: str,
    html_text: str | None = None,
    title_override: str = ""
) -> ParsedDocumentResponse:
    """
    Esegue il parser corretto e uniforma l'output al dominio assegnato.
    """
    parser_class = get_parser_class(domain)
    parser = parser_class(url)

    try:
        if html_text is not None:
            if hasattr(parser, "get_data_from_html_text"):
                data = await parser.get_data_from_html_text(
                    html_text=html_text,
                    title_override=title_override
                )
            else:
                temp_file = parser.save_html_text(html_text)
                data = await parser.build_data_from_html_file(
                    file_path=temp_file,
                    title_override=title_override
                )
        else:
            data = await parser.get_data()
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"URL irraggiungibile o parsing fallito: {exc}"
        ) from exc

    if "error" in data:
        raise HTTPException(
            status_code=502,
            detail="URL irraggiungibile o parsing fallito."
        )

    data["domain"] = domain
    return ParsedDocumentResponse(**data)


def aggregate_evaluations(results: list[dict[str, Any]]) -> EvaluationResponse:
    """
    Aggrega le metriche tramite media aritmetica delle singole entry del GS.
    """
    if not results:
        raise HTTPException(
            status_code=404,
            detail="Il Gold Standard del dominio richiesto è vuoto."
        )

    token_level_eval = {
        metric_name: round(
            mean(result["token_level_eval"][metric_name] for result in results),
            4
        )
        for metric_name in ("precision", "recall", "f1")
    }

    x_eval_keys = results[0].get("x_eval", {}).keys()
    x_eval = {
        metric_name: round(
            mean(result["x_eval"][metric_name] for result in results),
            4
        )
        for metric_name in x_eval_keys
    }

    return EvaluationResponse(
        token_level_eval=MetricTriple(**token_level_eval),
        x_eval=x_eval
    )


@app.get("/", tags=["system"])
async def root() -> dict[str, str]:
    """
    Endpoint informativo minimo per verificare che il backend sia avviato.
    """
    return {"message": "Backend avviato correttamente."}


@app.get("/domains", response_model=DomainsResponse, tags=["domains"])
async def get_domains() -> DomainsResponse:
    """
    Restituisce la lista dei domini assegnati.
    """
    return DomainsResponse(domains=load_assigned_domains())


@app.get("/parse", response_model=ParsedDocumentResponse, tags=["parser"])
async def parse_document(url: str) -> ParsedDocumentResponse:
    """
    Esegue il parser per l'URL richiesto.
    """
    normalized_url, domain = normalize_url_and_domain(url)
    return await run_parser(url=normalized_url, domain=domain)


@app.post("/parse", response_model=ParsedDocumentResponse, tags=["parser"])
async def parse_html_document(
    payload: ParseFromHtmlRequest
) -> ParsedDocumentResponse:
    """
    Esegue il parser usando l'URL solo per selezionare il dominio corretto e
    processando direttamente l'HTML inviato nel body della richiesta.
    """
    normalized_url, domain = normalize_url_and_domain(payload.url)

    if not payload.html_text.strip():
        raise HTTPException(
            status_code=400,
            detail="Il campo html_text non puo' essere vuoto."
        )

    return await run_parser(
        url=normalized_url,
        domain=domain,
        html_text=payload.html_text
    )


@app.get(
    "/gold_standard",
    response_model=GoldStandardEntryResponse,
    tags=["gold-standard"]
)
async def get_gold_standard(url: str) -> GoldStandardEntryResponse:
    """
    Restituisce l'entry del Gold Standard associata all'URL richiesto.
    """
    normalized_url, domain = normalize_url_and_domain(url)
    entry = find_gold_standard_entry(normalized_url, domain)
    entry["domain"] = domain
    return GoldStandardEntryResponse(**entry)


@app.get(
    "/full_gold_standard",
    response_model=FullGoldStandardResponse,
    tags=["gold-standard"]
)
async def get_full_gold_standard(domain: str) -> FullGoldStandardResponse:
    """
    Restituisce tutte le entry del Gold Standard per il dominio richiesto.
    """
    normalized_domain = match_assigned_domain(domain)
    if normalized_domain is None:
        raise HTTPException(
            status_code=400,
            detail="Dominio non supportato."
        )

    entries = load_gold_standard_entries(normalized_domain)
    normalized_entries = []

    for entry in entries:
        entry_copy = dict(entry)
        entry_copy["domain"] = normalized_domain
        normalized_entries.append(GoldStandardEntryResponse(**entry_copy))

    return FullGoldStandardResponse(gold_standard=normalized_entries)


@app.post("/evaluate", response_model=EvaluationResponse, tags=["evaluation"])
async def evaluate_document(payload: EvaluationRequest) -> EvaluationResponse:
    """
    Calcola le metriche di evaluation tra parsed_text e gold_text.
    """
    return EvaluationResponse(**evaluate_all(payload.parsed_text, payload.gold_text))


@app.get("/full_gs_eval", response_model=EvaluationResponse, tags=["evaluation"])
async def evaluate_full_gold_standard(domain: str) -> EvaluationResponse:
    """
    Riesegue il parsing di tutte le entry del GS del dominio e ne aggrega le
    metriche.
    """
    normalized_domain = match_assigned_domain(domain)
    if normalized_domain is None:
        raise HTTPException(
            status_code=400,
            detail="Dominio non supportato."
        )

    entries = load_gold_standard_entries(normalized_domain)
    evaluation_results = []

    for entry in entries:
        parsed_document = await run_parser(
            url=entry["url"],
            domain=normalized_domain,
            html_text=entry["html_text"],
            title_override=entry.get("title", "")
        )
        evaluation_results.append(
            evaluate_all(parsed_document.parsed_text, entry["gold_text"])
        )

    return aggregate_evaluations(evaluation_results)
# ===== FINE MODIFICHE IVAN =====

#main per testare da terminale senza API
async def main():
    target_url = "https://it.wikipedia.org/wiki/BabelNet"
    print(f"--- Avvio parsing di: {target_url} ---")
    
    parser = ParserWikipedia(target_url)
    data = await parser.get_data()

    if data:
        print("\n✅ ESTRAZIONE COMPLETATA CON SUCCESSO!")
        print(f"Titolo: {data['title']}")
        print(f"Dominio: {data['domain']}")
        #print("\n--- Anteprima Parsed Text (Markdown) ---")
        # Mostriamo solo i primi 3000 caratteri del testo pulito
        #print(data['parsed_text'][:3000] + "...")
        
        # Opzionale: salva il risultato in un file JSON per vederlo bene
        with open("test_wikipedia.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print("\n💾 Risultato completo salvato in 'test_wikipedia.json'")

        #salviamo anche solamente l'md in modo che sia più leggibile
        markdown_content = data.get("parsed_text", "")
        with open("parsed_text.md", "w", encoding="utf-8") as f:
            f.write(markdown_content)

        print("\n💾 markdown salvato in ''parsed_text.md'")        

if __name__ == "__main__":
    asyncio.run(main())
