from crawl4ai import CrawlerRunConfig, CacheMode
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from .parserBase import ParserBase
from .md_cleaning import clean_markdown_noise, clean_markdown_regex

class ParserLimes(ParserBase):
    
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
    
            #analizzando la struttura della pagina del sito notiamo che le informazioni per noi rilevanti sono
            #sempre contenute all'interno di un article con classe story e, all'interno di quest'ultimo le info
            #sono contenute all'interno di tutte le classi che contengono nel loro nome le stringhe:
            #'story' e 'content' insieme.
            #Prendere questo selettore quindi permette di escludere già in partenza gran parte del rumore della
            #pagina accettando un rischio molto basso di perdersi delle informazioni contenute in altri tag
            #della pagina.
            css_selector = 'article.story [class*="story"][class*="content"]',

            #successivamente escludiamo alcuni tag e alcuni selettori nelle classi per rimuovere contenuti di disturbo
            #dal corpo dell'articolo o anche per rimuovere i titoli delle pagine (che vengono presi a parte)
            excluded_tags = ["script", "style", "noscript", "iframe", "svg", "canvas", "form", "button", "figure", "hr"],
            excluded_selector = "ol.breadcrumb, .share,.social,[class*='share'],[id*='share'],.tags,[class*='tag'],[rel='tag'],[class*='embed'], [class*='date'], [class*='sidebar'], [class^='story'][class*='title']",

            word_count_threshold= 0, #altrimenti potrebbe essere invalidante
    
            markdown_generator= md_generator
        )   

        return config

    def clean_markdown(self, raw_markdown: str) -> str:
        """
        Pulizia avanzata del Markdown per LimesOnline.
        Rimuove boilerplate, metadati, note e residui di formattazione.
        """
        text = raw_markdown

        if not text:
            return ""
        
        #Filtro frasi con indicatori di rumore
        noise_indicators = ["continua a leggere","leggi anche","qui il link", "hanno collaborato"]
        text = clean_markdown_noise(text, noise_indicators)

        #Filtro regex
        substitution_rules =  [
            # rimuove separatori tipo * * * oppure *** 
            #(r"^\s*(\*\s*){3,}\s*$", "\n"),

            # collassa spazi multipli
            (r"[ \t]+", " "),

            # collassa 3+ newline in 2
            (r"\n{3,}", "\n\n"),
        ]
        text = clean_markdown_regex(text, substitution_rules)

        return text