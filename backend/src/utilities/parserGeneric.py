"""
Parser generico per pagine HTML senza configurazione specifica di dominio.

Viene usato come implementazione di riferimento e come fallback quando non
esiste un parser dedicato. La pulizia si limita a rimuovere immagini, link
e spazi in eccesso.
"""

import re

from crawl4ai import CrawlerRunConfig, CacheMode
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

from .parserBase import ParserBase


class ParserGeneric(ParserBase):
    """
    Parser generico che non applica alcuna selezione CSS specifica.
    Adatto a qualsiasi pagina HTML standard; produce risultati accettabili
    ma meno precisi rispetto ai parser di dominio.
    """

    def set_crawler(self) -> CrawlerRunConfig:
        """Configurazione minimale: esclude solo tag non informativi."""
        return CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            excluded_tags=["script", "style", "nav", "footer", "noscript"],
            word_count_threshold=0,
            markdown_generator=DefaultMarkdownGenerator(
                options={"ignore_links": True, "ignore_images": True, "body_width": 0}
            )
        )

    def clean_markdown(self, markdown_output: str) -> str:
        """Pulizia di base: rimuove immagini, link e spazi multipli."""
        text = markdown_output or ""

        substitution_rules = [
            (r"!\[.*?\]\(.*?\)",   ""),          # immagini markdown
            (r"\[([^\]]+)\]\(.*?\)", r"\1"),     # link → solo testo
            (r"[ \t]{2,}",          " "),         # spazi orizzontali multipli
            (r"\n{3,}",             "\n\n"),      # righe vuote eccessive
        ]

        for pattern, replacement in substitution_rules:
            text = re.sub(pattern, replacement, text)

        return text.strip()
