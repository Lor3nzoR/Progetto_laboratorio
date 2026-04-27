"""
Parser specializzato per limesonline.com.

Strategia di estrazione:
- CSS selector: article.story [class*="story"][class*="content"]
  Seleziona solo il corpo degli articoli, escludendo header, sidebar e widget.
  La scelta di combinare le classi "story" e "content" riduce il rumore già
  prima del post-processing, con un rischio molto basso di perdere contenuto.
- Esclusi: breadcrumb, pulsanti di condivisione, tag, date, titoli di sezione.
- Post-processing: rimozione di frasi di navigazione ("continua a leggere",
  link a video/audio) e pulizia regex dei separatori residui.

Nota: la difficoltà principale di questo dominio è distinguere link isolati
e frasi di rimando ("il video dell'evento:") dal testo informativo reale.
"""

from crawl4ai import CrawlerRunConfig, CacheMode
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

from .parserBase import ParserBase
from utilities.md_cleaning import clean_markdown_noise, clean_markdown_regex


class ParserLimes(ParserBase):
    """Parser per articoli di limesonline.com."""

    def set_crawler(self) -> CrawlerRunConfig:
        """
        Seleziona il corpo dell'articolo escludendo tutti gli elementi
        di navigazione e condivisione presenti nel layout del sito.
        """
        return CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            css_selector='article.story [class*="story"][class*="content"]',
            excluded_tags=["script", "style", "noscript", "iframe", "svg",
                           "canvas", "form", "button", "figure", "hr"],
            excluded_selector=(
                "ol.breadcrumb, .share, .social, [class*='share'], [id*='share'], "
                ".tags, [class*='tag'], [rel='tag'], [class*='embed'], "
                "[class*='date'], [class*='sidebar'], [class^='story'][class*='title']"
            ),
            word_count_threshold=0,
            markdown_generator=DefaultMarkdownGenerator(
                options={"ignore_links": True, "ignore_images": True, "body_width": 0}
            )
        )

    def clean_markdown(self, raw_markdown: str) -> str:
        """
        Pulizia in due passaggi:
        1. Rimozione righe con indicatori di navigazione/rimando.
        2. Pulizia regex: separatori, riferimenti a media esterni, spazi multipli.
        """
        text = raw_markdown
        if not text:
            return ""

        noise_indicators = ["continua a leggere", "leggi anche", "qui il link", "hanno collaborato"]
        text = clean_markdown_noise(text, noise_indicators)

        substitution_rules = [
            # Separatori tipo * * * o ***
            (r"^\s*(?:\*\s*)+$", ""),
            # Righe che puntano a media esterni ("il video dell'evento:", "qui il podcast:", ecc.)
            (
                r"^\s*(?:qui\s+(?:il\s+)?)?(?:il\s+)?(?:video|link|audio|podcast)"
                r"(?:\s+(?:dell[\'']evento|della\s+puntata|per\s+partecipare"
                r"(?:\s+all[\'']evento)?|youtube))?\s*:?\s*$",
                "",
            ),
            # Spazi orizzontali multipli.
            (r"[ \t]+", " "),
            # Righe vuote eccessive.
            (r"\n{3,}", "\n\n"),
        ]
        text = clean_markdown_regex(text, substitution_rules)

        return text
