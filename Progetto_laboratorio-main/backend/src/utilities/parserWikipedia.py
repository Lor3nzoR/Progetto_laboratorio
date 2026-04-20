from pathlib import Path
<<<<<<< HEAD
from crawl4ai import CrawlerRunConfig, CacheMode
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from .parserBase import ParserBase
from .md_cleaning import clean_markdown_by_sections, clean_markdown_noise, clean_markdown_regex

class ParserWikipedia(ParserBase):
=======
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from .parserBase import ParserBase
import re
from .md_cleaning import clean_markdown_by_sections

class ParserWikipedia(ParserBase):
    async def get_data(self) -> dict:
        #come primo step recuperiamo il percorso del raw_html
        file_path = await self.get_raw_html()
        return await self.build_data_from_html_file(file_path)

    # ===== INIZIO CODICE SCRITTO DA CODEX =====
    async def get_data_from_html_text(
        self,
        html_text: str,
        title_override: str = ""
    ) -> dict:
        """
        Permette di rieseguire il parser a partire dall'HTML salvato nel Gold
        Standard senza effettuare una nuova richiesta HTTP.
        """
        file_path = self.save_html_text(html_text)
        return await self.build_data_from_html_file(
            file_path=file_path,
            title_override=title_override
        )
    # ===== FINE CODICE SCRITTO DA CODEX =====
>>>>>>> a6cf71b (Commit iniziale)
    
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
<<<<<<< HEAD
        noise_indicators = ["pagina è semiprotetta", "voce in vetrina", "Questa voce è stata selezionata", "modifica wikitesto"]
        text = clean_markdown_noise(text, noise_indicators)

        # PULIZIA REGEX (Ordinata per priorità)
=======
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
>>>>>>> a6cf71b (Commit iniziale)
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
<<<<<<< HEAD

            # display di formule nel modo corretto
            (r'[^ \n\r\t][^\n{]{0,50}?\{\\displaystyle\s*(.*?)\s*\}', r'$\1$'),

            # Collassa 3 o più newline in massimo 2 (mantiene i paragrafi ma toglie il vuoto)
            (r'\n{3,}', '\n\n')
        ]

        text = clean_markdown_regex(text, substitution_rules)

        return text
=======
        ]

        for pattern, replacement in substitution_rules:
            text = re.sub(pattern, replacement, text)

        # 3. NORMALIZZAZIONE SPAZIATURA (Final Polish)
        # Rimuove spazi bianchi all'inizio/fine di ogni riga
        text = "\n".join(line.strip() for line in text.split('\n'))
    
        # Collassa 3 o più newline in massimo 2 (mantiene i paragrafi ma toglie il vuoto)
        text = re.sub(r'\n{3,}', '\n\n', text)

        return text.strip()
>>>>>>> a6cf71b (Commit iniziale)
