"""
Server FastAPI del progetto.

Questo file espone gli endpoint richiesti dalla consegna:
- GET /parse
- POST /parse
- GET /domains
- GET /gold_standard
- GET /full_gold_standard
- POST /evaluate
- GET /full_gs_eval

Tutto il codice aggiunto e' racchiuso nei marcatori richiesti, cosi' e'
semplice distinguere questa implementazione dal codice precedente.
"""

# ===== INIZIO CODICE SCRITTO DA CODEX =====

# Import standard: servono per leggere JSON, gestire percorsi e analizzare URL.
import json
from functools import lru_cache
from pathlib import Path
from statistics import mean
from typing import Any
from urllib.parse import urlparse

# Import FastAPI/Pydantic: servono per definire API REST, errori e modelli I/O.
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# Import dei moduli gia' presenti nel progetto.
from utilities.evaluation import evaluate_all
from utilities.parserGeneric import ParserGeneric
from utilities.parserWikipedia import ParserWikipedia
from utilities.parserWho import WHOParser


# Percorsi base del progetto.
# __file__ punta a backend/src/server.py, quindi parents[2] e' la root del progetto.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# File con i domini assegnati.
DOMAINS_FILE = PROJECT_ROOT / "domains.json"

# Cartella che contiene i file Gold Standard.
GS_DIRECTORY = PROJECT_ROOT / "gs_data"


# Modello Pydantic dell'output del parsing.
# Serve sia per GET /parse sia per POST /parse.
class ParsedDocumentResponse(BaseModel):
    url: str
    domain: str
    title: str
    html_text: str
    parsed_text: str


# Modello Pydantic di una entry del Gold Standard.
# La differenza principale rispetto al parsing e' il campo gold_text.
class GoldStandardEntryResponse(BaseModel):
    url: str
    domain: str
    title: str
    html_text: str
    gold_text: str


# Modello Pydantic della risposta di GET /domains.
class DomainsResponse(BaseModel):
    domains: list[str]


# Modello Pydantic della risposta di GET /full_gold_standard.
class FullGoldStandardResponse(BaseModel):
    gold_standard: list[GoldStandardEntryResponse]


# Modello Pydantic del body di POST /parse.
# L'URL serve a scegliere il parser corretto, html_text e' l'HTML da parsare.
class ParseFromHtmlRequest(BaseModel):
    url: str = Field(description="URL usato per selezionare il parser corretto.")
    html_text: str = Field(description="HTML grezzo da parsare direttamente.")


# Modello Pydantic del body di POST /evaluate.
# parsed_text e gold_text sono i due testi da confrontare.
class EvaluationRequest(BaseModel):
    parsed_text: str = Field(default="", description="Testo parsato in markdown.")
    gold_text: str = Field(default="", description="Testo gold senza markdown.")


# Modello Pydantic per precision/recall/f1.
# Viene usato dentro la risposta delle metriche obbligatorie.
class MetricTriple(BaseModel):
    precision: float
    recall: float
    f1: float


# Modello Pydantic della risposta di POST /evaluate e GET /full_gs_eval.
# token_level_eval e' obbligatoria; x_eval contiene metriche aggiuntive.
class EvaluationResponse(BaseModel):
    token_level_eval: MetricTriple
    x_eval: dict[str, float]


# Creazione dell'app FastAPI.
# Uvicorn carica questa variabile con "server:app".
app = FastAPI(
    title="Web Parsing Backend",
    description="Backend REST per parsing, Gold Standard ed evaluation.",
    version="1.1.0"
)


# Cache della lettura dei domini.
# Evita di rileggere domains.json a ogni richiesta.
@lru_cache(maxsize=1)
def load_assigned_domains() -> list[str]:
    """
    Legge domains.json e restituisce solo le stringhe dei domini assegnati.
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


# Normalizzazione del dominio.
# Permette di accettare sia "who.int" sia host come "www.who.int".
def match_assigned_domain(host_or_domain: str) -> str | None:
    """
    Restituisce il dominio assegnato corrispondente a host_or_domain.
    """
    normalized_host = host_or_domain.strip().lower()

    for assigned_domain in load_assigned_domains():
        if normalized_host == assigned_domain:
            return assigned_domain
        if normalized_host.endswith(f".{assigned_domain}"):
            return assigned_domain

    return None


# Validazione URL.
# Centralizza i controlli usati da GET /parse, POST /parse e GET /gold_standard.
def normalize_url_and_domain(url: str) -> tuple[str, str]:
    """
    Controlla che l'URL sia valido e appartenga a un dominio assegnato.
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


# Selezione parser.
# MODIFICA: mappatura esplicita di tutti i 4 domini assegnati.
# Nessun dominio viene trattato come caso speciale a livello di server.
def get_parser_class(domain: str):
    """
    Restituisce la classe parser corretta per il dominio richiesto.
    """
    specific_parsers = {
        "it.wikipedia.org": ParserWikipedia,
        "limesonline.com": ParserGeneric,
        "yahoo.com": ParserGeneric,
        "who.int": WHOParser
    }

    parser_class = specific_parsers.get(domain)
    if parser_class is None:
        raise ValueError(f"Nessun parser registrato per il dominio: {domain}")

    return parser_class


# Percorso del Gold Standard.
# Converte ad esempio "it.wikipedia.org" in "it_wikipedia_org_gs.json".
def get_gs_file_path(domain: str) -> Path:
    """
    Ricava il file JSON del Gold Standard associato a un dominio.
    """
    return GS_DIRECTORY / f"{domain.replace('.', '_')}_gs.json"


# Lettura del Gold Standard.
# Restituisce sempre una lista, anche se il file contenesse un solo oggetto.
def load_gold_standard_entries(domain: str) -> list[dict[str, Any]]:
    """
    Carica tutte le entry del Gold Standard per un dominio.
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


# Ricerca entry Gold Standard.
# Serve all'endpoint GET /gold_standard.
def find_gold_standard_entry(url: str, domain: str) -> dict[str, Any]:
    """
    Cerca nel GS l'entry associata all'URL richiesto.
    """
    for entry in load_gold_standard_entries(domain):
        if entry.get("url") == url:
            return entry

    raise HTTPException(
        status_code=404,
        detail="L'URL richiesto non e' presente nel Gold Standard."
    )


# Parsing da URL.
# Usa il metodo get_data() del parser, che scarica la pagina e produce l'output.
async def parse_from_url(url: str, domain: str) -> ParsedDocumentResponse:
    """
    Esegue il parsing scaricando la pagina dall'URL.
    """
    parser_class = get_parser_class(domain)
    parser = parser_class(url)

    try:
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


# Parsing da HTML diretto.
# Questo implementa la richiesta aggiornata del PDF 1.1.0 per POST /parse.
async def parse_from_html(
    url: str,
    domain: str,
    html_text: str,
    title_override: str = ""
) -> ParsedDocumentResponse:
    """
    Esegue il parsing partendo da una stringa HTML gia' disponibile.
    """
    parser_class = get_parser_class(domain)
    parser = parser_class(url)

    try:
        # MODIFICA: delega uniforme al parser di dominio.
        data = await parser.parse_html(
            html_text=html_text,
            title_override=title_override
        )

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Parsing HTML fallito: {exc}"
        ) from exc

    if "error" in data:
        raise HTTPException(
            status_code=502,
            detail="Parsing HTML fallito."
        )

    data["domain"] = domain
    return ParsedDocumentResponse(**data)


# Aggregazione metriche.
# full_gs_eval richiede la media delle metriche sulle entry del Gold Standard.
def aggregate_evaluations(results: list[dict[str, Any]]) -> EvaluationResponse:
    """
    Calcola la media delle metriche prodotte sui documenti del GS.
    """
    if not results:
        raise HTTPException(
            status_code=404,
            detail="Il Gold Standard del dominio richiesto e' vuoto."
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


# Endpoint di controllo.
# Utile per verificare rapidamente che il container backend sia partito.
@app.get("/", tags=["system"])
async def root() -> dict[str, str]:
    """
    Restituisce un messaggio minimale di stato.
    """
    return {"message": "Backend avviato correttamente."}


# Endpoint domini.
# La risposta deve contenere solo la lista dei domini supportati.
@app.get("/domains", response_model=DomainsResponse, tags=["domains"])
async def get_domains() -> DomainsResponse:
    """
    Restituisce la lista dei domini assegnati.
    """
    return DomainsResponse(domains=load_assigned_domains())


# Endpoint GET /parse.
# Scarica la pagina dall'URL e restituisce HTML grezzo e testo pulito.
@app.get("/parse", response_model=ParsedDocumentResponse, tags=["parser"])
async def parse_document(url: str) -> ParsedDocumentResponse:
    """
    Esegue il parsing di una pagina partendo dal suo URL.
    """
    normalized_url, domain = normalize_url_and_domain(url)
    return await parse_from_url(normalized_url, domain)


# Endpoint POST /parse.
# Usa l'URL solo per scegliere il parser e parsifica direttamente html_text.
@app.post("/parse", response_model=ParsedDocumentResponse, tags=["parser"])
async def parse_html_document(
    payload: ParseFromHtmlRequest
) -> ParsedDocumentResponse:
    """
    Esegue il parsing di HTML diretto inviato nel body della richiesta.
    """
    normalized_url, domain = normalize_url_and_domain(payload.url)

    if not payload.html_text.strip():
        raise HTTPException(
            status_code=400,
            detail="Il campo html_text non puo' essere vuoto."
        )

    return await parse_from_html(
        url=normalized_url,
        domain=domain,
        html_text=payload.html_text
    )


# Endpoint Gold Standard singolo.
# Recupera una sola entry del GS usando l'URL come chiave.
@app.get(
    "/gold_standard",
    response_model=GoldStandardEntryResponse,
    tags=["gold-standard"]
)
async def get_gold_standard(url: str) -> GoldStandardEntryResponse:
    """
    Restituisce l'entry Gold Standard associata all'URL richiesto.
    """
    normalized_url, domain = normalize_url_and_domain(url)
    entry = dict(find_gold_standard_entry(normalized_url, domain))
    entry["domain"] = domain
    return GoldStandardEntryResponse(**entry)


# Endpoint Gold Standard completo.
# Restituisce tutte le entry del file GS associato al dominio.
@app.get(
    "/full_gold_standard",
    response_model=FullGoldStandardResponse,
    tags=["gold-standard"]
)
async def get_full_gold_standard(domain: str) -> FullGoldStandardResponse:
    """
    Restituisce tutto il Gold Standard di un dominio.
    """
    normalized_domain = match_assigned_domain(domain)
    if normalized_domain is None:
        raise HTTPException(
            status_code=400,
            detail="Dominio non supportato."
        )

    normalized_entries = []
    for entry in load_gold_standard_entries(normalized_domain):
        entry_copy = dict(entry)
        entry_copy["domain"] = normalized_domain
        normalized_entries.append(GoldStandardEntryResponse(**entry_copy))

    return FullGoldStandardResponse(gold_standard=normalized_entries)


# Endpoint evaluation.
# Non calcola metriche qui: riusa evaluate_all() gia' presente nel progetto.
@app.post("/evaluate", response_model=EvaluationResponse, tags=["evaluation"])
async def evaluate_document(payload: EvaluationRequest) -> EvaluationResponse:
    """
    Confronta parsed_text e gold_text restituendo le metriche.
    """
    return EvaluationResponse(**evaluate_all(payload.parsed_text, payload.gold_text))


# Endpoint evaluation aggregata.
# Rilegge l'HTML del GS, lo riparsa e calcola la media delle metriche.
@app.get("/full_gs_eval", response_model=EvaluationResponse, tags=["evaluation"])
async def evaluate_full_gold_standard(domain: str) -> EvaluationResponse:
    """
    Valuta tutte le entry del Gold Standard di un dominio.
    """
    normalized_domain = match_assigned_domain(domain)
    if normalized_domain is None:
        raise HTTPException(
            status_code=400,
            detail="Dominio non supportato."
        )

    evaluation_results = []

    for entry in load_gold_standard_entries(normalized_domain):
        parsed_document = await parse_from_html(
            url=entry["url"],
            domain=normalized_domain,
            html_text=entry["html_text"],
            title_override=entry.get("title", "")
        )

        evaluation_results.append(
            evaluate_all(parsed_document.parsed_text, entry["gold_text"])
        )

    return aggregate_evaluations(evaluation_results)

# ===== FINE CODICE SCRITTO DA CODEX =====
