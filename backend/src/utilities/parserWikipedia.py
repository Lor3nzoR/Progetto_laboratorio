from pathlib import Path
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from .parserBase import ParserBase
import re
from .md_cleaning import clean_markdown_by_sections

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
            cleaned_text = self.clean_markdown(result.markdown.raw_markdown) #result.markdown.raw_markdown 

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
        # Creiamo il generatore di Markdown con le opzioni desiderate
        md_generator = DefaultMarkdownGenerator(
            options={
                "ignore_links": True,   # Rimuove i link mantenendo il testo
                "ignore_images": True,  # Rimuove le immagini
                "body_width": 0         # Impedisce l'andata a capo automatica forzata
            }
        )

        config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            css_selector="div.mw-parser-output",
    
            # NOTA: Qui usiamo una stringa, non una lista!
            excluded_selector=".hatnote, .ambox, .infobox, .mw-indicators, .metadata, .topicon, .mediaContainer, .noexcerpt, .noprint, .mw-empty-elt",
    
            # excluded_tags invece di solito accetta una lista, 
            # ma se vuoi andare sul sicuro, controlla se l'errore persiste
            excluded_tags=['table', 'style', 'script', 'nav', 'figure'],

            word_count_threshold= 0, #altrimenti potrebbe essere invalidante
    
            markdown_generator= md_generator
        )   

        return config

    def clean_markdown(self, text: str) -> str:
        """
        Pulizia avanzata del Markdown per Wikipedia.
        Rimuove boilerplate, metadati, note e residui di formattazione.
        """
        if not text:
            return ""
        
        # FILTRO SEZIONI
        #rimuoviamo sezioni indesiderrate
        noise_sections = ["note", "bibliografia", "voci correlate", "altri progetti", "collegamenti esterni", "premi"]
        text = clean_markdown_by_sections(text, noise_sections)

        # FILTRO RIGHE
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