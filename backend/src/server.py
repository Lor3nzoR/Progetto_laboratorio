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
    target_url = "https://it.wikipedia.org/wiki/Equazione_di_Schr%C3%B6dinger"
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