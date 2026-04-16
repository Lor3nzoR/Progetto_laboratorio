from abc import ABC, abstractmethod
from urllib.parse import urlparse
import asyncio
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.content_filter_strategy import PruningContentFilter
import re
import json
from bs4 import BeautifulSoup
from markdownify import markdownify as md

class ParserBase(ABC):

    def __init__(self, url):
        self.url : str = url #url completo
        self.domain : str = urlparse(url).netloc #dominio che servirà in output
        self.crawl_config = self.set_config() #configurazione del crawl
        self.browser_config = self.set_browser() #configurazione del browser

    @abstractmethod
    async def get_data(self) -> dict:
        """
        metodo per restituire in output i dati parsati nel formato richiesto
        """
        pass

    def set_config(self) -> CrawlerRunConfig:
        """
        Attualmente conviene configurare il crawler con i valori di default
        in modo da poter ottenere l'html grezzo intero della pagina
        """
        config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
        )   
        return config

    def set_browser(self) -> BrowserConfig:
        """
        metodo uguale per tutti i parser per settare le configurazioni di browser.
        Possiamo sovrascriverlo in modo più specifico all'occorrenza
        """
        return BrowserConfig(
            # Headless: True per i server, False se si vuole vedere cosa succede
            headless=True,
        
            # lasciamo il valore di default
            browser_type="chromium",
    )

    @abstractmethod
    def clean_markdown(self, markdown_output : str):
        """
        metodo per ripulire il markdown restituito da Crawl4ai in base al dominio specifico 
        tramite regex ed eventuali altre manipolazioni
        """
        pass


#Paser per Wikipedia
class ParserWikipedia(ParserBase):
    async def get_data(self) -> dict:
        async with AsyncWebCrawler(config=self.browser_config) as crawler:
            # 1. Eseguiamo il crawl e prendiamo l'html grezzo
            result = await crawler.arun(url=self.url, config=self.crawl_config)
            
            if not result.success:
                return {"error": "Failed to crawl"}

            # 2. utilizziamo Beautifulsosup per: 
            # - Parsare l'html grezzo 
            # - Eliminare elementi strutturali di disturbo

            """
            La tattica è cercare la classe 'mw-parser-output' che contiene tutto il
            testo informativo della pagina (tranne il titolo) con degli elementi di disturbo.
            Visto però che a volte questa classe è presente più volte nel testo html, usiamo prima 
            l'id del corpo testuale e poi cerchiamo al suo interno la classe
            """

            soup = BeautifulSoup(result.html, 'html.parser')
        
            # Invece di cercare subito la classe, cerchiamo l'ID unico del corpo testuale
            container = soup.find(id="mw-content-text")

            if container:
                # Cerchiamo il div mw-parser-output che è FIGLIO di mw-content-text
                corpo_centrale = container.find('div', class_='mw-parser-output', recursive=False)
    
                # Se recursive=False non lo trova (a seconda della versione di Wiki), usa:
                if not corpo_centrale:
                    corpo_centrale = container.find('div', class_='mw-parser-output')

                if corpo_centrale:
                    # Rimuoviamo gli elementi di disturbo
                    for element in corpo_centrale.select('.hatnote, .ambox, .infobox, .mw-indicators, .metadata, table, sup, figure, .mw-empty-elt'):
                        element.decompose()
        
                    # Estraiamo il testo convertendolo in markdown
                    testo_estratto = md(str(corpo_centrale))
        
                    # Pulizia finale con le Regex
                    cleaned_text = self.clean_markdown(testo_estratto)

            # Restituiamo esattamente la struttura richiesta dall'esonero
            return {
                "url": self.url,
                "domain": self.domain,
                "title": result.metadata.get('title', ''),
                "html_text": result.html,           # HTML grezzo
                "parsed_text": cleaned_text         # Markdown pulito
            }
    
    def clean_markdown(self, markdown_output) -> str:
        """Pulizia finale post-parsing per un testo 'Gold Standard'"""
        # 1. TRASFORMA IL TESTO IN RIGHE PER FILTRARE IL RUMORE
        lines = markdown_output.split('\n')
        cleaned_lines = []
    
        for line in lines:
            l_strip = line.strip()
            # Salta la riga se contiene icone di protezione o vetrina
            if "pagina è semiprotetta" in l_strip or "voce in vetrina" in l_strip:
                continue
            # Salta righe che sono solo un'immagine Markdown residua
            if l_strip.startswith("![") or l_strip == "![]":
                continue
            cleaned_lines.append(line)
    
        text = '\n'.join(cleaned_lines)

        # 2. RIMUOVI TUTTE LE IMMAGINI RESIDUE ![alt](url)
        # Questa regex è più aggressiva: prende tutto ciò che inizia con ![ e finisce con )
        text = re.sub(r'!\[.*?\]\([^)]+\)', '', text)

        # 3. IL RESTO DELLA TUA PULIZIA (Link e Note)
        # Trasforma i link rimasti in parole: [Dante](url) -> Dante
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
        # Elimina URL solitari tra parentesi (quelli delle date)
        text = re.sub(r'\(\s*https?://[^\s)]+(?:\s+"[^"]*")?\s*\)', '', text)
        # Elimina note tipo [1], [2], [modifica]
        text = re.sub(r'\[modifica\s*\|\s*modifica wikitesto\]|\[\d+\]|\[N\s*\d+\]', '', text)
    
        return text.strip()

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
        print("\n--- Anteprima Parsed Text (Markdown) ---")
        # Mostriamo solo i primi 3000 caratteri del testo pulito
        print(data['parsed_text'][:3000] + "...")
        
        # Opzionale: salva il risultato in un file JSON per vederlo bene
        with open("test_wikipedia.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print("\n💾 Risultato completo salvato in 'test_wikipedia.json'")
        

if __name__ == "__main__":
    asyncio.run(main())