from crawl4ai import CrawlerRunConfig, CacheMode
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from .parserBase import ParserBase
from .md_cleaning import clean_markdown_by_sections, clean_markdown_noise, clean_markdown_regex

class ParserWikipedia(ParserBase):
    
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
        noise_indicators = ["pagina è semiprotetta", "voce in vetrina", "Questa voce è stata selezionata", "modifica wikitesto"]
        text = clean_markdown_noise(text, noise_indicators)

        # PULIZIA REGEX (Ordinata per priorità)
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

            # display di formule nel modo corretto
            (r'[^ \n\r\t][^\n{]{0,50}?\{\\displaystyle\s*(.*?)\s*\}', r'$\1$'),

            # Collassa 3 o più newline in massimo 2 (mantiene i paragrafi ma toglie il vuoto)
            (r'\n{3,}', '\n\n')
        ]

        text = clean_markdown_regex(text, substitution_rules)

        return text