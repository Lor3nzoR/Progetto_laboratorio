import os
from pathlib import Path
import asyncio
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from .parserBase import ParserBase
import re

class ParserWikipedia(ParserBase):
    async def get_data(self) -> dict:

        #come primo step recuperiamo il percorso del raw_html
        file_path = await self.get_raw_html()
        #lo convertiamo nell'uri da passare al crawler
        local_html = f"file://{file_path}"

        async with AsyncWebCrawler(config=self.browser_config) as crawler:
            # 1. Eseguiamo il crawl e prendiamo l'html grezzo
            result = await crawler.arun(url=local_html, config=self.crawl_config)
            
            if not result.success:
                return {"error": "Failed to crawl"}

            # Puliamo il testo usando il metodo della classe base
            cleaned_text = self.clean_markdown(result.markdown.raw_markdown)

            #recuriamo il contenuto del raw html per restituirlo in output
            html_grezzo = Path(file_path).read_text(encoding="utf-8")

            # Restituiamo esattamente la struttura richiesta dall'esonero
            return {
                "url": self.url,
                "domain": self.domain,
                "title": result.metadata.get('title', ''),
                "html_text": html_grezzo,           # HTML grezzo
                "parsed_text": cleaned_text         # Markdown pulito
            }
    
    def set_crawler(self):
        config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            css_selector="div.mw-parser-output",
    
            # NOTA: Qui usiamo una stringa, non una lista!
            excluded_selector=".hatnote, .ambox, .infobox, .mw-indicators, .metadata, .topicon, .mediaContainer, .noexcerpt, .noprint, .mw-empty-elt",
    
            # excluded_tags invece di solito accetta una lista, 
            # ma se vuoi andare sul sicuro, controlla se l'errore persiste
            excluded_tags=['table', 'style', 'script', 'nav', 'sup', 'figure'],
    
            word_count_threshold=25
        )   

        return config

    def clean_markdown(self, text: str) -> str:
        """
        Pulizia avanzata del Markdown per Wikipedia.
        Rimuove boilerplate, metadati, note e residui di formattazione.
        """
        if not text:
            return ""

        # 1. FILTRO RIGHE (Noise Reduction)
        # Definiamo frasi tipiche dei metadati/avvisi di Wikipedia
        noise_indicators = {
            "pagina è semiprotetta", 
            "voce in vetrina", 
            "Questa voce è stata selezionata",
            "modifica wikitesto"
        }
    
        lines = text.split('\n')
        cleaned_lines = []
    
        for line in lines:
            l_strip = line.strip()
            # Salta righe vuote o indicatori di rumore
            if not l_strip or any(indicator in l_strip for indicator in noise_indicators):
                continue
            # Salta righe che sono puramente immagini Markdown
            if l_strip.startswith("![") or l_strip == "![]":
                continue
            cleaned_lines.append(line)

        text = '\n'.join(cleaned_lines)

        # 2. PULIZIA REGEX (Ordinata per priorità)
        substitution_rules = [
            # Rimozione Immagini: ![alt](url)
            (r'!\[.*?\]\(.*?\)', ''),
        
            # Trasformazione Link in solo testo: [testo](url) -> testo
            (r'\[([^\]]+)\]\(.*?\)', r'\1'),
        
            # Rimozione note e citazioni: [1], [23], [N 1], [modifica], [modifica wikitesto]
            (r'\[(?:modifica|N\s*)?\d*\]|\[modifica\s*\|\s*modifica wikitesto\]', ''),
        
            # Rimozione URL solitari tra parentesi (spesso dopo le date)
            (r'\(\s*https?://[^\s)]+\s*\)', ''),
        
            # Rimozione di spazi multipli orizzontali (ma non i newline)
            (r'[ \t]{2,}', ' '),
        ]

        for pattern, replacement in substitution_rules:
            text = re.sub(pattern, replacement, text)

        # 3. NORMALIZZAZIONE SPAZIATURA (Final Polish)
        # Rimuove spazi bianchi all'inizio/fine di ogni riga
        text = "\n".join(line.strip() for line in text.split('\n'))
    
        # Collassa 3 o più newline in massimo 2 (mantiene i paragrafi ma toglie il vuoto)
        text = re.sub(r'\n{3,}', '\n\n', text)

        return text.strip()