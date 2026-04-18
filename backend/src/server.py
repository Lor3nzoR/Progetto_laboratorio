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

#main per testare da terminale senza API
async def main():
    target_url = "https://it.wikipedia.org/wiki/Firenze"
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
        

if __name__ == "__main__":
    asyncio.run(main())