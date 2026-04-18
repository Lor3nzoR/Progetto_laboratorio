import json
import asyncio
import os
import time

# Importiamo il parser dalla directory utilities
from utilities.parserWikipedia import ParserWikipedia
# Importiamo la funzione di valutazione finale
from utilities.evaluation import evaluate_all

# =====================================================================
# CONFIGURAZIONE TEST RAPIDI
# Aggiungi qui gli URL troppo lunghi che bloccano le metriche quadratiche
# =====================================================================
URL_DA_SALTARE = [
    "https://it.wikipedia.org/wiki/Roma",
    "https://it.wikipedia.org/wiki/Seconda_guerra_mondiale"
]


def print_metric_legend():
    """
    Stampa a schermo una legenda chiara per spiegare come interpretare i risultati.
    """
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


async def run_evaluation_on_gs():
    """
    Legge il file Gold Standard, filtra gli URL pesanti, avvia il parser 
    e calcola le metriche tenendo traccia dei tempi.
    """
    print_metric_legend()
    print("--- INIZIO VALUTAZIONE GOLD STANDARD (VERSIONE RAPIDA) ---")

    # 1. Costruiamo il percorso assoluto
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))
    gs_file_path = os.path.join(project_root, "gs_data", "it_wikipedia_org_gs.json")

    # 2. Carichiamo il JSON
    try:
        with open(gs_file_path, "r", encoding="utf-8") as f:
            gs_data = json.load(f)
    except FileNotFoundError:
        print(f"❌ Errore: File non trovato in {gs_file_path}")
        return

    if isinstance(gs_data, dict):
        gs_data = [gs_data]

    # 3. Applichiamo il filtro rapido
    gs_data_filtrato = [item for item in gs_data if item.get("url") not in URL_DA_SALTARE]
    documenti_saltati = len(gs_data) - len(gs_data_filtrato)
    
    print(f"⏭️  Filtro attivo: scartati {documenti_saltati} documenti pesanti.")
    print(f"⚙️  Analisi dei {len(gs_data_filtrato)} documenti rimanenti in corso...\n")

    # Avvio Timer Totale
    total_start_time = time.perf_counter()

    # 4. Iteriamo solo sui documenti filtrati
    for idx, item in enumerate(gs_data_filtrato, start=1):
        url = item.get("url")
        gold_text = item.get("gold_text")
        
        print(f"[{idx}/{len(gs_data_filtrato)}] Analizzando URL: {url}")
        
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

    # Fine Timer Totale
    total_end_time = time.perf_counter()
    total_duration = total_end_time - total_start_time

    print("\n" + "=" * 70)
    print(f"🏁 VALUTAZIONE RAPIDA COMPLETATA IN {total_duration:.2f} SECONDI")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_evaluation_on_gs())