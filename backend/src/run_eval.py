import json
import asyncio
import os
import time

from utilities.parserWikipedia import ParserWikipedia
from utilities.evaluation import evaluate_all

# =====================================================================
# CONFIGURAZIONE TEST RAPIDI
# =====================================================================
URL_DA_SALTARE = [
    "https://it.wikipedia.org/wiki/Roma",
    "https://it.wikipedia.org/wiki/Seconda_guerra_mondiale"
]


def print_metric_legend():
    print("=" * 70)
    print("🔍 LEGENDA DELLE METRICHE DI VALUTAZIONE")
    print("=" * 70)
    print("• Token-Level F1 (Metrica Base):")
    print("  Cosa fa: Valuta la sovrapposizione esatta dei set di parole estratte vs oro.")
    print("  Score: 1.0 (Perfetto, parole esatte) -> 0.0 (Pessimo, nessuna parola in comune)")
    print("\n• Character-Level F1 (x_eval):")
    print("  Cosa fa: Rileva il 'rumore microscopico' (tag HTML residui, punteggiatura spuria).")
    print("  Score: 1.0 (Perfetto, testo pulitissimo) -> 0.0 (Pessimo, solo rumore)")
    print("\n• Jaccard Similarity (x_eval):")
    print("  Cosa fa: Indica il livello di sovrapposizione globale (Intersezione su Unione).")
    print("  Score: 1.0 (Insiemi identici) -> 0.0 (Insiemi disgiunti)")
    print("\n• Word Error Rate - WER (x_eval):")
    print("  Cosa fa: Distanza di editing. Quante operazioni servono per correggere il testo.")
    print("  Score: 0.0 (Perfetto, nessuna correzione) -> Più sale, peggio è (indica rumore o perdite)")
    print("\n• ROUGE-L F1 (x_eval):")
    print("  Cosa fa: Valuta l'integrità della frase e l'ordine delle parole (LCS).")
    print("  Score: 1.0 (Struttura perfetta) -> 0.0 (Ordine spezzato o testo stravolto)")
    print("=" * 70 + "\n")


def scegli_modalita(gs_data: list) -> list:
    """
    Mostra un menu interattivo e restituisce la lista di documenti
    filtrata in base alla scelta dell'utente.
    """
    tutti_gli_url = [item.get("url") for item in gs_data]

    print("=" * 70)
    print("⚙️  SELEZIONA LA MODALITÀ DI ESECUZIONE")
    print("=" * 70)
    print("  [1] Tutti i documenti        — include anche quelli pesanti")
    print("  [2] Modalità rapida          — esclude gli URL in URL_DA_SALTARE")
    print("  [3] Scegli un URL specifico  — seleziona manualmente dalla lista")
    print("=" * 70)

    while True:
        scelta = input("👉 Inserisci il numero della modalità (1/2/3): ").strip()

        if scelta == "1":
            print(f"\n✅ Modalità: TUTTI ({len(gs_data)} documenti)\n")
            return gs_data

        elif scelta == "2":
            filtrato = [item for item in gs_data if item.get("url") not in URL_DA_SALTARE]
            saltati = len(gs_data) - len(filtrato)
            print(f"\n✅ Modalità: RAPIDA — scartati {saltati} documenti pesanti, rimangono {len(filtrato)}\n")
            return filtrato

        elif scelta == "3":
            print("\n📋 URL disponibili:")
            for i, url in enumerate(tutti_gli_url, start=1):
                marker = " ⚠️ (pesante)" if url in URL_DA_SALTARE else ""
                print(f"  [{i}] {url}{marker}")

            while True:
                try:
                    idx_url = int(input(f"\n👉 Inserisci il numero dell'URL (1-{len(tutti_gli_url)}): ").strip())
                    if 1 <= idx_url <= len(tutti_gli_url):
                        selezionato = [gs_data[idx_url - 1]]
                        print(f"\n✅ Modalità: SINGOLO URL — {tutti_gli_url[idx_url - 1]}\n")
                        return selezionato
                    else:
                        print(f"❌ Numero fuori range. Inserisci un valore tra 1 e {len(tutti_gli_url)}.")
                except ValueError:
                    print("❌ Input non valido. Inserisci un numero intero.")

        else:
            print("❌ Scelta non valida. Inserisci 1, 2 o 3.")


async def run_evaluation_on_gs():
    print_metric_legend()
    print("--- INIZIO VALUTAZIONE GOLD STANDARD ---")

    # 1. Percorso assoluto al file GS
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))
    gs_file_path = os.path.join(project_root, "gs_data", "it_wikipedia_org_gs.json")

    # 2. Caricamento JSON
    try:
        with open(gs_file_path, "r", encoding="utf-8") as f:
            gs_data = json.load(f)
    except FileNotFoundError:
        print(f"❌ Errore: File non trovato in {gs_file_path}")
        return

    if isinstance(gs_data, dict):
        gs_data = [gs_data]

    # 3. Selezione modalità interattiva
    gs_data_selezionato = scegli_modalita(gs_data)

    # 4. Avvio timer totale
    total_start_time = time.perf_counter()

    # 5. Iterazione sui documenti selezionati
    for idx, item in enumerate(gs_data_selezionato, start=1):
        url = item.get("url")
        gold_text = item.get("gold_text")

        print(f"[{idx}/{len(gs_data_selezionato)}] Analizzando URL: {url}")

        doc_start_time = time.perf_counter()

        parser = ParserWikipedia(url)
        parsed_data = await parser.get_data()

        if "error" in parsed_data:
            print(f"❌ Fallimento durante il crawling di: {url}")
            continue

        parsed_text = parsed_data["parsed_text"]

        print("Calcolo delle metriche in corso...")
        evaluation_results = evaluate_all(parsed_text, gold_text)

        doc_end_time = time.perf_counter()

        print("✅ Risultati Evaluation:")
        print(json.dumps(evaluation_results, indent=4))
        print(f"⏱  Tempo di crawling e analisi: {doc_end_time - doc_start_time:.2f} secondi")
        print("-" * 70)

    # 6. Fine timer totale
    total_end_time = time.perf_counter()
    total_duration = total_end_time - total_start_time

    print("\n" + "=" * 70)
    print(f"🏁 VALUTAZIONE COMPLETATA IN {total_duration:.2f} SECONDI")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_evaluation_on_gs())