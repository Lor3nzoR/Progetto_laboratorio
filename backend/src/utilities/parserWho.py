from crawl4ai import CrawlerRunConfig, CacheMode
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

from .parserBase import ParserBase
from .md_cleaning import (
    clean_markdown_by_sections,
    clean_markdown_noise,
    clean_markdown_regex,
)


class WHOParser(ParserBase):
    def supports(self, url: str) -> bool:
        return "who.int" in self.domain

    def set_crawler(self):
        md_generator = DefaultMarkdownGenerator(
            options={
                "ignore_links": True,
                "ignore_images": True,
                "body_width": 0,
            }
        )

        return CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,

            # Il contenuto WHO è quasi sempre dentro main/article
            css_selector="main, article, [role='main']",

            # Escludiamo il boilerplate più comune del template WHO
            excluded_selector="""
                header, nav, footer, aside,
                .sf-top-header, .sf-header, .sf-footer,
                .sf-geo-navigation, .main-navigation, .top-header,
                .breadcrumb, .breadcrumbs,
                .social-share, .share, .language-selector,
                .translation-links, .donate, .newsletter,
                .related-links, .related, .promo, .banner,
                .sf-list-vertical__item, .sf-publications-item,
                .sf-multimedia-item, .slicknav_menu,
                .alphabetical-nav, .navigation, .region-picker,
                .sf-image-credit
            """,

            excluded_tags=["style", "script", "nav", "footer", "aside", "form", "button", "svg"],

            word_count_threshold=0,
            markdown_generator=md_generator,
        )

    def clean_markdown(self, text: str) -> str:
        if not text:
            return ""

        # Taglia sezioni che spesso nelle pagine WHO sono secondarie
        noise_sections = [
            "related",
            "related links",
            "more",
            "multimedia",
            "publications",
            "documents",
            "resources",
            "databases",
            "tools",
            "news",
            "initiatives and groups",
            "feature stories",
            "events",
            "section navigation",
        ]
        text = clean_markdown_by_sections(text, noise_sections)

        # Righe tipiche di boilerplate
        noise_indicators = [
            "skip to main content",
            "select language",
            "world health organization",
            "home /",
            "health topics",
            "countries",
            "newsroom",
            "emergencies",
            "about who",
        ]
        text = clean_markdown_noise(text, noise_indicators)

        substitution_rules = [
            # immagini markdown
            (r'!\[.*?\]\(.*?\)', ''),

            # link markdown -> solo testo
            (r'\[([^\]]+)\]\(.*?\)', r'\1'),

            # spazi multipli
            (r'[ \t]{2,}', ' '),

            # righe composte solo da separatori tipo ===
            (r'^\s*[=\-]{3,}\s*$', '',),

            # spazio prima della punteggiatura
            (r'\s+([,.;:!?])', r'\1'),

            # numeri ordinali spezzati: 7 th -> 7th
            (r'(\d)\s+(st|nd|rd|th)\b', r'\1\2'),

            # troppe righe vuote
            (r'\n{3,}', '\n\n'),
        ]

        text = clean_markdown_regex(text, substitution_rules)

        lines = [line.strip() for line in text.splitlines()]

        cleaned_lines = []
        seen = set()

        for line in lines:
            if not line:
                cleaned_lines.append("")
                continue

            low = line.lower()

            # scarta righe troppo da navigazione
            if low in {
                "related",
                "more",
                "multimedia",
                "publications",
                "documents",
                "resources",
                "databases",
                "tools",
                "news",
            }:
                continue

            sig = " ".join(low.split())
            if sig in seen:
                continue
            seen.add(sig)
            cleaned_lines.append(line)

        text = "\n".join(cleaned_lines)
        text = clean_markdown_regex(text, [(r'\n{3,}', '\n\n')])

        return text.strip()