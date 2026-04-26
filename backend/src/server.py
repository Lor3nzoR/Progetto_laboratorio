
import json
from functools import lru_cache
from pathlib import Path
from statistics import mean
from typing import Any
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from utilities.evaluation import evaluate_all
from utilities.gsEvalCache import get_cached_full_gs_eval
from utilities.gsParseCache import get_cached_parsed_entry
from utilities.parserBase import ParserBase
from utilities.parserWikipedia import ParserWikipedia
from utilities.parserWho import WHOParser
from utilities.parserLimes import ParserLimes
from utilities.parserYahooFinance import ParserYahooFinance


# __file__ punta a backend/src/server.py → parents[2] è la root del progetto.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

DOMAINS_FILE = PROJECT_ROOT / "domains.json"
GS_DIRECTORY = PROJECT_ROOT / "gs_data"
FULL_GS_EVAL_MAX_TEXT_BUDGET = 60000

PUBLIC_TO_CANONICAL_DOMAIN = {
    "it.wikipedia.org": "it.wikipedia.org",
    "www.limesonline.com": "limesonline.com",
    "finance.yahoo.com": "finance.yahoo.com",
    "www.who.int": "who.int",
}


# ---------------------------------------------------------------------------
# Modelli Pydantic
# ---------------------------------------------------------------------------

class ParsedDocumentResponse(BaseModel):
    """Risposta degli endpoint GET /parse e POST /parse."""
    url: str
    domain: str
    title: str
    html_text: str
    parsed_text: str


class GoldStandardEntryResponse(BaseModel):
    """Singola entry del Gold Standard (contiene gold_text invece di parsed_text)."""
    url: str
    domain: str
    title: str
    html_text: str
    gold_text: str


class DomainsResponse(BaseModel):
    """Risposta di GET /domains."""
    domains: list[str]


class FullGoldStandardResponse(BaseModel):
    """Risposta di GET /full_gold_standard."""
    gold_standard: list[GoldStandardEntryResponse]


class ParseFromHtmlRequest(BaseModel):
    """Body di POST /parse: l'URL serve solo a scegliere il parser corretto."""
    url: str = Field(description="URL usato per selezionare il parser corretto.")
    html_text: str = Field(description="HTML grezzo da parsare direttamente.")


class EvaluationRequest(BaseModel):
    """Body di POST /evaluate."""
    parsed_text: str = Field(default="", description="Testo parsato in markdown.")
    gold_text: str = Field(default="", description="Testo gold senza markdown.")


class MetricTriple(BaseModel):
    """Tripla precision / recall / F1 usata in EvaluationResponse."""
    precision: float
    recall: float
    f1: float


class EvaluationResponse(BaseModel):
    """Risposta di POST /evaluate e GET /full_gs_eval."""
    token_level_eval: MetricTriple
    x_eval: dict[str, float]


# ---------------------------------------------------------------------------
# Applicazione FastAPI
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Web Parsing Backend",
    description="Backend REST per parsing, Gold Standard ed evaluation.",
    version="1.1.0"
)


# ---------------------------------------------------------------------------
# Funzioni di supporto
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def load_assigned_domains() -> list[str]:
    """
    Legge domains.json e restituisce la lista delle stringhe dei domini assegnati.
    Il risultato è memorizzato in cache: il file viene letto una sola volta.
    """
    if not DOMAINS_FILE.exists():
        return []

    content = json.loads(DOMAINS_FILE.read_text(encoding="utf-8"))
    domains = []

    for item in content.get("domini_assegnati", []):
        domain = str(item.get("domain", "")).strip().lower()
        if domain:
            domains.append(domain)

    return domains


def match_assigned_domain(host_or_domain: str) -> str | None:
    """
    Restituisce il dominio assegnato corrispondente a host_or_domain.
    Accetta sia il dominio esatto ("who.int") sia sottodomini ("www.who.int").
    """
    normalized = host_or_domain.strip().lower()

    for assigned in load_assigned_domains():
        canonical = PUBLIC_TO_CANONICAL_DOMAIN.get(assigned, assigned)
        if (
            normalized == assigned
            or normalized.endswith(f".{assigned}")
            or normalized == canonical
            or normalized.endswith(f".{canonical}")
        ):
            return assigned

    return None


def canonicalize_domain(domain: str) -> str:
    """
    Converte il dominio pubblico esposto dal backend nel dominio canonico
    usato internamente per parser e file del Gold Standard.
    """
    return PUBLIC_TO_CANONICAL_DOMAIN.get(domain, domain)


def normalize_url_and_domain(url: str) -> tuple[str, str]:
    """
    Valida l'URL e verifica che appartenga a un dominio assegnato.
    Solleva HTTPException 400 se l'URL non è valido o il dominio non è supportato.
    """
    normalized_url = url.strip()
    parsed = urlparse(normalized_url)

    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=400, detail="URL non valido. Usare un URL HTTP o HTTPS.")

    domain = match_assigned_domain(parsed.netloc)
    if domain is None:
        raise HTTPException(status_code=400, detail="Dominio non supportato.")

    return normalized_url, domain


def get_parser_class(domain: str) -> type[ParserBase]:
    """
    Restituisce la classe parser registrata per il dominio richiesto.
    Solleva ValueError se il dominio non ha un parser dedicato.
    """
    parsers = {
        "it.wikipedia.org": ParserWikipedia,
        "limesonline.com":  ParserLimes,
        "finance.yahoo.com": ParserYahooFinance,
        "who.int":          WHOParser,
    }

    parser_class = parsers.get(canonicalize_domain(domain))
    if parser_class is None:
        raise ValueError(f"Nessun parser registrato per il dominio: {domain}")

    return parser_class


def get_gs_file_path(domain: str) -> Path:
    """
    Converte il nome di un dominio nel percorso del file JSON del Gold Standard.
    Es.: "it.wikipedia.org" → gs_data/it_wikipedia_org_gs.json
    """
    canonical_domain = canonicalize_domain(domain)
    return GS_DIRECTORY / f"{canonical_domain.replace('.', '_')}_gs.json"


@lru_cache(maxsize=4)
def load_gold_standard_entries(domain: str) -> list[dict[str, Any]]:
    """
    Carica tutte le entry del Gold Standard per il dominio indicato.
    Il risultato è memorizzato in cache (un entry per dominio, 4 domini in totale):
    i file GS non cambiano durante il ciclo di vita del server.
    Solleva HTTPException 404 se il file non esiste.
    """
    gs_file = get_gs_file_path(domain)

    if not gs_file.exists():
        raise HTTPException(
            status_code=404,
            detail="Gold Standard non disponibile per il dominio richiesto."
        )

    content = json.loads(gs_file.read_text(encoding="utf-8"))
    # Il file può contenere un oggetto singolo o una lista di oggetti.
    return [content] if isinstance(content, dict) else content


def find_gold_standard_entry(url: str, domain: str) -> dict[str, Any]:
    """
    Cerca nel Gold Standard l'entry con l'URL esatto fornito.
    Solleva HTTPException 404 se l'URL non è presente nel GS.
    """
    for entry in load_gold_standard_entries(domain):
        if entry.get("url") == url:
            return entry

    raise HTTPException(
        status_code=404,
        detail="L'URL richiesto non è presente nel Gold Standard."
    )


async def parse_from_url(url: str, domain: str) -> ParsedDocumentResponse:
    """
    Scarica la pagina dall'URL e la parsifica con il parser del dominio.
    Solleva HTTPException 502 se la pagina non è raggiungibile o il parsing fallisce.
    """
    parser = get_parser_class(domain)(url)

    try:
        data = await parser.get_data()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Parsing fallito: {exc}") from exc

    if "error" in data:
        raise HTTPException(status_code=502, detail="URL irraggiungibile o parsing fallito.")

    data["domain"] = domain
    return ParsedDocumentResponse(**data)


async def parse_from_html(
    url: str,
    domain: str,
    html_text: str,
    title_override: str = ""
) -> ParsedDocumentResponse:
    """
    Parsifica una stringa HTML già disponibile (usato da POST /parse e full_gs_eval).
    Il parametro title_override permette di passare il titolo dal Gold Standard.
    """
    cached_entry = get_cached_parsed_entry(domain=domain, url=url, html_text=html_text)
    if cached_entry is not None:
        return ParsedDocumentResponse(
            url=url,
            domain=domain,
            title=title_override or cached_entry.get("title", ""),
            html_text=html_text,
            parsed_text=cached_entry.get("parsed_text", ""),
        )

    parser = get_parser_class(domain)(url)

    try:
        data = await parser.parse_html(html_text=html_text, title_override=title_override)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Parsing HTML fallito: {exc}") from exc

    if "error" in data:
        raise HTTPException(status_code=502, detail="Parsing HTML fallito.")

    data["domain"] = domain
    return ParsedDocumentResponse(**data)


def aggregate_evaluations(results: list[dict[str, Any]]) -> EvaluationResponse:
    """
    Calcola la media aritmetica di tutte le metriche su più documenti.
    Usata da GET /full_gs_eval per restituire un valore aggregato per dominio.
    """
    if not results:
        raise HTTPException(status_code=404, detail="Il Gold Standard del dominio è vuoto.")

    token_level_eval = {
        metric: round(mean(r["token_level_eval"][metric] for r in results), 4)
        for metric in ("precision", "recall", "f1")
    }

    x_eval_keys = results[0].get("x_eval", {}).keys()
    x_eval = {
        metric: round(mean(r["x_eval"][metric] for r in results), 4)
        for metric in x_eval_keys
    }

    return EvaluationResponse(
        token_level_eval=MetricTriple(**token_level_eval),
        x_eval=x_eval
    )


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@app.get("/", tags=["system"])
async def root() -> dict[str, str]:
    """Endpoint di controllo: verifica che il container backend sia avviato."""
    return {"message": "Backend avviato correttamente."}


@app.get("/domains", response_model=DomainsResponse, tags=["domains"])
async def get_domains() -> DomainsResponse:
    """Restituisce la lista dei domini assegnati letti da domains.json."""
    return DomainsResponse(domains=load_assigned_domains())


@app.get("/parse", response_model=ParsedDocumentResponse, tags=["parser"])
async def parse_document(url: str) -> ParsedDocumentResponse:
    """Scarica la pagina dall'URL e restituisce HTML grezzo e testo pulito."""
    normalized_url, domain = normalize_url_and_domain(url)
    return await parse_from_url(normalized_url, domain)


@app.post("/parse", response_model=ParsedDocumentResponse, tags=["parser"])
async def parse_html_document(payload: ParseFromHtmlRequest) -> ParsedDocumentResponse:
    """Parsifica l'HTML fornito nel body senza effettuare richieste di rete."""
    normalized_url, domain = normalize_url_and_domain(payload.url)

    if not payload.html_text.strip():
        raise HTTPException(status_code=400, detail="Il campo html_text non può essere vuoto.")

    return await parse_from_html(url=normalized_url, domain=domain, html_text=payload.html_text)


@app.get("/gold_standard", response_model=GoldStandardEntryResponse, tags=["gold-standard"])
async def get_gold_standard(url: str) -> GoldStandardEntryResponse:
    """Restituisce l'entry del Gold Standard associata all'URL richiesto."""
    normalized_url, domain = normalize_url_and_domain(url)
    entry = dict(find_gold_standard_entry(normalized_url, domain))
    entry["domain"] = domain
    return GoldStandardEntryResponse(**entry)


@app.get("/full_gold_standard", response_model=FullGoldStandardResponse, tags=["gold-standard"])
async def get_full_gold_standard(domain: str) -> FullGoldStandardResponse:
    """Restituisce tutto il Gold Standard del dominio richiesto."""
    normalized_domain = match_assigned_domain(domain)
    if normalized_domain is None:
        raise HTTPException(status_code=400, detail="Dominio non supportato.")

    entries = []
    for entry in load_gold_standard_entries(normalized_domain):
        entry_copy = dict(entry)
        entry_copy["domain"] = normalized_domain
        entries.append(GoldStandardEntryResponse(**entry_copy))

    return FullGoldStandardResponse(gold_standard=entries)


@app.post("/evaluate", response_model=EvaluationResponse, tags=["evaluation"])
async def evaluate_document(payload: EvaluationRequest) -> EvaluationResponse:
    """Confronta parsed_text con gold_text e restituisce le metriche di qualità."""
    return EvaluationResponse(**evaluate_all(payload.parsed_text, payload.gold_text))


@app.get("/full_gs_eval", response_model=EvaluationResponse, tags=["evaluation"])
async def evaluate_full_gold_standard(domain: str) -> EvaluationResponse:
    """
    Parsifica ogni entry del Gold Standard di un dominio e calcola
    la media delle metriche su tutti i documenti.
    """
    normalized_domain = match_assigned_domain(domain)
    if normalized_domain is None:
        raise HTTPException(status_code=400, detail="Dominio non supportato.")

    cached_evaluation = get_cached_full_gs_eval(normalized_domain)
    if cached_evaluation is not None:
        return EvaluationResponse(**cached_evaluation)

    results = []
    for entry in load_gold_standard_entries(normalized_domain):
        parsed = await parse_from_html(
            url=entry["url"],
            domain=normalized_domain,
            html_text=entry["html_text"],
            title_override=entry.get("title", "")
        )

        # Allinea /full_gs_eval ai documenti che il grader riesce anche a
        # reinviare a POST /evaluate nel controllo di coerenza manuale.
        if len(parsed.parsed_text) + len(entry["gold_text"]) > FULL_GS_EVAL_MAX_TEXT_BUDGET:
            continue

        results.append(evaluate_all(parsed.parsed_text, entry["gold_text"]))

    return aggregate_evaluations(results)
