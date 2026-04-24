import json
import asyncio
import os

# Assicurati che il nome importato corrisponda al tuo file reale
from utilities.parserYahoo_daHtml import ParserYahooFinanceHtml


async def extract_to_md():
    print("=" * 70)
    print("📝 ESTRAZIONE TESTO DA HTML (YAHOO FINANCE) A OUTPUT.MD")
    print("=" * 70)

    # 1. Percorso assoluto al file GS
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))
    gs_file_path = os.path.join(project_root, "gs_data", "finance_yahoo_com_gs.json")
    
    # Il file di output verrà creato in backend/src/
    output_file_path = os.path.join(current_dir, "output.md")

    # 2. Caricamento JSON
    try:
        with open(gs_file_path, "r", encoding="utf-8") as f:
            gs_data = json.load(f)
    except FileNotFoundError:
        print(f"❌ Errore: File non trovato in {gs_file_path}")
        return

    if isinstance(gs_data, dict):
        gs_data = [gs_data]

    # 3. Selezione interattiva del documento
    print("\n📋 URL disponibili nel file JSON:")
    for i, item in enumerate(gs_data, start=1):
        print(f"  [{i}] {item.get('url', 'Sconosciuto')}")

    while True:
        try:
            scelta = int(input(f"\n👉 Inserisci il numero del documento da estrarre (1-{len(gs_data)}): ").strip())
            if 1 <= scelta <= len(gs_data):
                documento = gs_data[scelta - 1]
                break
            else:
                print(f"❌ Numero fuori range. Inserisci un valore tra 1 e {len(gs_data)}.")
        except ValueError:
            print("❌ Input non valido. Inserisci un numero intero.")

    url = documento.get("url", "URL_SCONOSCIUTO")
    raw_html = documento.get("html_text", "")

    if not raw_html:
        print("❌ Nessun HTML trovato nel file GS per questo documento.")
        return

    print(f"\n⏳ Parsing in corso per: {url} ...")

    # 4. Inizializzazione parser ed estrazione
    parser = ParserYahooFinanceHtml(url=url, domain="finance.yahoo.com", raw_html=raw_html)
    parsed_data = await parser.get_data()

    if "error" in parsed_data:
        print(f"❌ Errore durante il parsing: {parsed_data['error']}")
        return

    parsed_text = parsed_data.get("parsed_text", "")

    # 5. Salvataggio su file
    with open(output_file_path, "w", encoding="utf-8") as f:
        f.write(parsed_text)

    print(f"✅ Parsing completato con successo!")
    print(f"📂 Il testo estratto è stato salvato in: {output_file_path}")


if __name__ == "__main__":
    asyncio.run(extract_to_md())