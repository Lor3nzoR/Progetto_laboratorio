from crawl4ai import CrawlerRunConfig, CacheMode
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
import re

from .parserBase import ParserBase


# ===== INIZIO CODICE SCRITTO DA CODEX =====
class ParserGeneric(ParserBase):
    async def get_data(self) -> dict:
        """
        Parser minimale di fallback per i domini assegnati che non hanno ancora
        una logica dedicata.
        """
        file_path = await self.get_raw_html()
        return await self.build_data_from_html_file(file_path)

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
