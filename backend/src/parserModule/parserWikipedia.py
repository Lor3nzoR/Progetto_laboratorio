"""
Parser specializzato per it.wikipedia.org.

Strategia di estrazione:
- CSS selector: div.mw-parser-output
  Seleziona il contenitore standard del corpo voce, riducendo gia in input
  gran parte del rumore strutturale della pagina.
- Esclusi: hatnote, avvisi, infobox, indicatori, metadata e media container.
- Post-processing in 3 fasi:
  1. Rimozione delle sezioni enciclopediche finali non narrative.
  2. Eliminazione di righe boilerplate e avvisi editoriali.
  3. Pulizia regex di note, link, URL residui e formule.

Nota: su Wikipedia il rumore piu frequente non e nell'HTML principale,
ma nei richiami editoriali e nelle note numerate disperse nel testo.
"""

from crawl4ai import CrawlerRunConfig, CacheMode
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
import re
import html

from .parserBase import ParserBase
from utilities.md_cleaning import clean_markdown_by_sections, clean_markdown_noise, clean_markdown_regex


class ParserWikipedia(ParserBase):
    """Parser per pagine del dominio it.wikipedia.org."""

    def set_crawler(self) -> CrawlerRunConfig:
        """
        Seleziona il corpo della voce escludendo box informativi ed elementi
        accessori che Wikipedia inserisce nel markup principale.
        """
        md_generator = DefaultMarkdownGenerator(
            options={
                "ignore_links": True,
                "ignore_images": True,
                "body_width": 0,
            }
        )

        return CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            css_selector="div.mw-parser-output",
            excluded_selector=".hatnote, .ambox, .infobox, .mw-indicators, .metadata, .topicon, .mediaContainer, .noexcerpt, .noprint, .mw-empty-elt",
            excluded_tags=["style", "script", "nav", "figure"],
            word_count_threshold=0,
            markdown_generator=md_generator,
        )
    
    def _preprocess_math(self, html_text: str) -> str:
        """
        Sostituisce ogni blocco <math>...</math> con il solo contenuto
        dell'annotation LaTeX, rimuovendo eventuali virgolette esterne.
        Serve per mostrare le formule lasciando solo l'annotation della formula.
        """

        def replace_math(match: re.Match) -> str:
            math_block = match.group(0)

            annotation_match = re.search(
                r'<annotation[^>]*encoding=["\']application/x-tex["\'][^>]*>(.*?)</annotation>',
                math_block,
                flags=re.DOTALL | re.IGNORECASE
            )

            if not annotation_match:
                return ""

            latex = annotation_match.group(1).strip()
            latex = html.unescape(latex)

            # Rimuove solo le virgolette esterne, se presenti
            if len(latex) >= 2 and latex[0] == '"' and latex[-1] == '"':
                latex = latex[1:-1]

            return latex

        return re.sub(
            r'<math[^>]*>.*?</math>',
            replace_math,
            html_text,
            flags=re.DOTALL | re.IGNORECASE
        )

    async def parse_html(self, html_text: str, title_override: str = "", crawler=None) -> dict:
        html_text = self._preprocess_math(html_text)
        return await super().parse_html(html_text, title_override, crawler)

    def clean_markdown(self, text: str) -> str:
        """
        Pulizia in 3 passaggi:
        1. Rimozione di sezioni finali non centrali per il contenuto.
        2. Filtro di righe con avvisi e metadati tipici di Wikipedia.
        3. Rifinitura regex di note, link, URL e spaziatura residua.
        """
        if not text:
            return ""

        noise_sections = ["note", "bibliografia", "voci correlate", "altri progetti", "collegamenti esterni"]
        text = clean_markdown_by_sections(text, noise_sections)

        # Indicatori editoriali ricorrenti che non appartengono al contenuto della voce.
        noise_indicators = ["pagina è semiprotetta", "voce in vetrina", "Questa voce è stata selezionata", "modifica wikitesto"]
        text = clean_markdown_noise(text, noise_indicators)

        # Le regex sono ordinate dal rumore piu strutturato alle rifiniture finali.
        substitution_rules = [
            (r'!\[.*?\]\(.*?\)', ''),
            (r'\[([^\]]+)\]\(.*?\)', r'\1'),
            (r'\[(?:modifica|N\s*)?\d*\]|\[modifica\s*\|\s*modifica wikitesto\]', ''),
            (r'\(\s*https?://[^\s)]+\s*\)', ''),
            (r'[ \t]{2,}', ' '),
            # Converte il wrapper LaTeX generato da Crawl4AI in una formula inline leggibile.
            (r'\{\\displaystyle\s+([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}', r'$\1$'),
            (r'\n{3,}', '\n\n'),
        ]

        text = clean_markdown_regex(text, substitution_rules)

        return text
