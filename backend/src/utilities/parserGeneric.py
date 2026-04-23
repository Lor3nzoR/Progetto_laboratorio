from crawl4ai import CrawlerRunConfig, CacheMode
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
import re

from .parserBase import ParserBase


# ===== INIZIO CODICE SCRITTO DA CODEX =====
class ParserGeneric(ParserBase):
    # MODIFICA: non ridefiniamo get_data(), cosi' ParserGeneric eredita
    # ParserBase.get_data(), che e' il metodo disponibile nel progetto attuale.
    # ELIMINATO: il vecchio get_data() chiamava build_data_from_html_file(),
    # ma quel metodo non esiste piu' in ParserBase e causava AttributeError.

    def set_crawler(self) -> CrawlerRunConfig:
        """
        Configurazione semplice, adatta a pagine HTML generiche.
        """
        md_generator = DefaultMarkdownGenerator(
            options={
                "ignore_links": True,
                "ignore_images": True,
                "body_width": 0
            }
        )

        return CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            excluded_tags=["script", "style", "nav", "footer", "noscript"],
            word_count_threshold=0,
            markdown_generator=md_generator
        )

    def clean_markdown(self, markdown_output: str) -> str:
        """
        Pulizia base del markdown per non specializzare troppo il parser.
        """
        cleaned_text = markdown_output or ""

        substitution_rules = [
            (r"!\[.*?\]\(.*?\)", ""),
            (r"\[([^\]]+)\]\(.*?\)", r"\1"),
            (r"[ \t]{2,}", " "),
            (r"\n{3,}", "\n\n")
        ]

        for pattern, replacement in substitution_rules:
            cleaned_text = re.sub(pattern, replacement, cleaned_text)

        return cleaned_text.strip()
# ===== FINE CODICE SCRITTO DA CODEX =====
