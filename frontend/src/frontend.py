import asyncio
import os
import time
from typing import Any

import httpx
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates


# URL del backend: configurabile tramite variabile d'ambiente (utile in Docker).
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8003").rstrip("/")

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

app = FastAPI(
    title="Web Parsing Frontend",
    description="Interfaccia web per il parsing e la valutazione dei domini assegnati.",
    version="1.1.0",
)

_CTX_TTL = 60.0

# Il lock va creato dentro il loop asyncio, non a livello di modulo.
# Viene inizializzato nell'evento di startup di FastAPI.
_ctx_lock: asyncio.Lock | None = None
_ctx_cache: dict[str, Any] = {}
_ctx_ts: float = 0.0


@app.on_event("startup")
async def startup() -> None:
    """Inizializza il lock della cache nel loop asyncio già attivo."""
    global _ctx_lock
    _ctx_lock = asyncio.Lock()


async def backend_request(
    method: str,
    endpoint: str,
    params: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    """
    Invia una richiesta HTTP asincrona al backend e restituisce (json, None)
    in caso di successo oppure (None, messaggio_errore) in caso di errore.
    Il timeout di 120 secondi copre i parsing piu lenti (es. Yahoo Finance con consenso GDPR).
    Usa httpx.AsyncClient per non bloccare l'event loop di FastAPI.
    """
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.request(
                method=method,
                url=f"{BACKEND_URL}{endpoint}",
                params=params,
                json=payload,
            )
    except httpx.RequestError as exc:
        return None, f"Il backend non e raggiungibile: {exc}"

    try:
        response_json = response.json()
    except ValueError:
        response_json = None

    if response.is_success:
        return response_json, None

    if isinstance(response_json, dict) and "detail" in response_json:
        return None, str(response_json["detail"])

    return None, f"Richiesta fallita con status code {response.status_code}."


async def load_page_context() -> dict[str, Any]:
    """
    Carica domini e GS dal backend; risultato in cache per 60 secondi.
    Il lock garantisce che richieste concorrenti non scatenino chiamate
    duplicate al backend durante il refresh della cache.
    """
    global _ctx_cache, _ctx_ts

    async with _ctx_lock:  # type: ignore[union-attr]
        if _ctx_cache and (time.monotonic() - _ctx_ts) < _CTX_TTL:
            return _ctx_cache

        domains_response, domains_error = await backend_request("GET", "/domains")
        domains = domains_response.get("domains", []) if domains_response else []

        gs_entries = []
        for domain in domains:
            gs_response, _ = await backend_request(
                "GET", "/full_gold_standard", params={"domain": domain}
            )
            if gs_response:
                gs_entries.extend(gs_response.get("gold_standard", []))

        gs_entries.sort(key=lambda entry: entry.get("url", ""))

        _ctx_cache = {
            "backend_url":   BACKEND_URL,
            "domains":       domains,
            "domains_error": domains_error,
            "gs_entries":    gs_entries,
        }
        _ctx_ts = time.monotonic()
        return _ctx_cache


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Renderizza la pagina iniziale con il form e gli URL del GS disponibili."""
    context = dict(await load_page_context())  # copia per non mutare la cache
    context.update({
        "request":       request,
        "selected_url":  "",
        "submitted_url": "",
        "parse_result":  None,
        "gold_standard": None,
        "evaluation":    None,
        "error_message": None,
    })
    return templates.TemplateResponse("index.html", context)


@app.post("/analyze", response_class=HTMLResponse)
async def analyze(
    request: Request,
    url: str = Form(default=""),
    selected_url: str = Form(default=""),
):
    """
    Esegue il parsing dell'URL richiesto (manuale o dal dropdown GS).
    Se l'URL e presente nel Gold Standard, mostra anche il confronto e le metriche.
    """
    context = dict(await load_page_context())  # copia per non mutare la cache
    # L'URL manuale ha priorita su quello selezionato dal dropdown.
    target_url = url.strip() or selected_url.strip()

    context.update({
        "request":       request,
        "selected_url":  selected_url,
        "submitted_url": url,
        "parse_result":  None,
        "gold_standard": None,
        "evaluation":    None,
        "error_message": None,
    })

    if not target_url:
        context["error_message"] = "Inserisci un URL oppure selezionane uno dal Gold Standard."
        return templates.TemplateResponse("index.html", context)

    parse_result, parse_error = await backend_request("GET", "/parse", params={"url": target_url})
    if parse_error:
        context["error_message"] = parse_error
        return templates.TemplateResponse("index.html", context)

    context["parse_result"] = parse_result

    # Il Gold Standard potrebbe non essere disponibile per l'URL inserito manualmente.
    gold_standard, gs_error = await backend_request(
        "GET", "/gold_standard", params={"url": target_url}
    )
    if not gs_error and gold_standard:
        context["gold_standard"] = gold_standard
        evaluation, evaluation_error = await backend_request(
            "POST",
            "/evaluate",
            payload={
                "parsed_text": parse_result["parsed_text"],
                "gold_text":   gold_standard["gold_text"],
            },
        )
        if evaluation_error:
            context["error_message"] = evaluation_error
        else:
            context["evaluation"] = evaluation

    return templates.TemplateResponse("index.html", context)