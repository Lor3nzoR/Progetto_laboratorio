# ===== INIZIO CODICE SCRITTO DA CODEX =====
import os
from typing import Any

import requests
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates


BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8003").rstrip("/")
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

app = FastAPI(
    title="Web Parsing Frontend",
    description="Interfaccia.",
    version="1.0.0"
)


def backend_request(
    method: str,
    endpoint: str,
    params: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None
) -> tuple[dict[str, Any] | None, str | None]:
    """
    Invia una richiesta al backend e restituisce JSON oppure messaggio di errore.
    """
    try:
        response = requests.request(
            method=method,
            url=f"{BACKEND_URL}{endpoint}",
            params=params,
            json=payload,
            timeout=120
        )
    except requests.RequestException as exc:
        return None, f"Il backend non è raggiungibile: {exc}"

    try:
        response_json = response.json()
    except ValueError:
        response_json = None

    if response.ok:
        return response_json, None

    if isinstance(response_json, dict) and "detail" in response_json:
        return None, str(response_json["detail"])

    return None, f"Richiesta fallita con status code {response.status_code}."


def load_page_context() -> dict[str, Any]:
    """
    Recupera domini e URL del Gold Standard per popolare la UI.
    """
    domains_response, domains_error = backend_request("GET", "/domains")
    domains = domains_response.get("domains", []) if domains_response else []

    gs_entries = []
    for domain in domains:
        gs_response, _ = backend_request(
            "GET",
            "/full_gold_standard",
            params={"domain": domain}
        )
        if gs_response:
            gs_entries.extend(gs_response.get("gold_standard", []))

    gs_entries.sort(key=lambda entry: entry.get("url", ""))

    return {
        "backend_url": BACKEND_URL,
        "domains": domains,
        "domains_error": domains_error,
        "gs_entries": gs_entries
    }


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """
    Renderizza la pagina iniziale con il form e gli URL del GS disponibili.
    """
    context = load_page_context()
    context.update(
        {
            "request": request,
            "selected_url": "",
            "submitted_url": "",
            "parse_result": None,
            "gold_standard": None,
            "evaluation": None,
            "error_message": None
        }
    )
    return templates.TemplateResponse("index.html", context)


@app.post("/analyze", response_class=HTMLResponse)
async def analyze(
    request: Request,
    url: str = Form(default=""),
    selected_url: str = Form(default="")
):
    """
    Esegue il parsing dell'URL richiesto e mostra eventuale confronto con il GS.
    """
    context = load_page_context()
    target_url = url.strip() or selected_url.strip()

    context.update(
        {
            "request": request,
            "selected_url": selected_url,
            "submitted_url": url,
            "parse_result": None,
            "gold_standard": None,
            "evaluation": None,
            "error_message": None
        }
    )

    if not target_url:
        context["error_message"] = "Inserisci un URL oppure selezionane uno dal Gold Standard."
        return templates.TemplateResponse("index.html", context)

    parse_result, parse_error = backend_request(
        "GET",
        "/parse",
        params={"url": target_url}
    )
    if parse_error:
        context["error_message"] = parse_error
        return templates.TemplateResponse("index.html", context)

    context["parse_result"] = parse_result

    gold_standard, gs_error = backend_request(
        "GET",
        "/gold_standard",
        params={"url": target_url}
    )
    if not gs_error and gold_standard:
        context["gold_standard"] = gold_standard
        evaluation, evaluation_error = backend_request(
            "POST",
            "/evaluate",
            payload={
                "parsed_text": parse_result["parsed_text"],
                "gold_text": gold_standard["gold_text"]
            }
        )
        if evaluation_error:
            context["error_message"] = evaluation_error
        else:
            context["evaluation"] = evaluation

    return templates.TemplateResponse("index.html", context)
# ===== FINE CODICE SCRITTO DA CODEX =====
