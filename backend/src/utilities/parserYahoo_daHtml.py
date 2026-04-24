import re
from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode, BrowserConfig
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from .parserBase import ParserBase
from .md_cleaning import clean_markdown_by_sections, clean_markdown_noise, clean_markdown_regex


class ParserYahooFinanceHtml(ParserBase):

    def __init__(self, url: str, domain: str, raw_html: str):
        super().__init__(url)
        self.domain = domain
        self.raw_html = raw_html

    def set_crawler(self) -> CrawlerRunConfig:
        return CrawlerRunConfig()

    def set_browser(self) -> BrowserConfig:
        return BrowserConfig()

    def _get_page_type(self) -> str:
        if "/quote/" in self.url:
            return "quote"
        elif any(p in self.url for p in ["/news/", "/m/", "/article/", "/story/"]):
            return "article"
        return "generic"

    def _build_excluded_selector(self, page_type: str) -> str:
        base = [
            "footer",
            "nav",
            "aside",
            ".consent-overlay",
            "#consent-page",
            "[data-testid='ad-container']",
            "[data-testid='tradenow-ad-container']",
            ".sdaContainer",
        ]

        quote_extra = [
            "[data-testid='quote-title']",
            ".topCta",
            ".bottomCta",
            ".event-banner",
            "[data-testid='chart-container']",
            "[data-testid='ticker-news-summary']",
            "[data-testid='recent-news']",
            "[data-testid='company-overview-card'] .footer",
            "[data-testid='earnings-trends']",
            "[data-testid='compare-to']",
            "[data-testid='people-also-watch']",
            "[data-testid='related-tickers']",
            "[data-testid='quote-events-list']",
        ]

        article_extra = [
            "header",                              # <-- solo qui
            "[data-testid='sidebar']",
            "[data-testid='related-articles']",
            "[data-testid='author-bio']",
            ".caas-readmore",
            ".caas-more-content",
            ".recommendations",
            # Yahoo Finance specifici
            "figcaption",                          # didascalie foto ("FILE PHOTO: ... · Reuters")
            ".byline",                             # barra autore/data/"N min read"
            ".ticker-list",                        # pillole ticker azionari inline
            ".readmore",                           # pulsante "Story Continues"
            ".article-footer",                     # footer Terms/Privacy
            ".cover-slideshow-wrapper",            # slideshow immagini
        ]

        if page_type == "quote":
            return ", ".join(base + quote_extra)   # no header, css_selector ci pensa
        elif page_type == "article":
            return ", ".join(base + article_extra)

        return ", ".join(base + ["header"])        # generic: header nel base

    def _build_css_selector(self, page_type: str) -> str | None:
        if page_type == "quote":
            return "main"              # esclude header/aside globali, preserva gli header interni
        elif page_type == "article":
            # Preferisce il body dell'articolo; evita 'article' o 'main' che trascinano
            # byline, figure e seamless scroll articles successivi
            return "[data-testid='article-body'], .caas-body"
        return "#main-content-wrapper"

    async def get_data(self) -> dict:
        if not self.raw_html or not self.raw_html.strip():
            return {"error": "Stringa HTML vuota fornita."}

        page_type = self._get_page_type()
        css_selector = self._build_css_selector(page_type)

        config_kwargs = dict(
            cache_mode=CacheMode.BYPASS,
            excluded_selector=self._build_excluded_selector(page_type),
            excluded_tags=["script", "style", "iframe", "noscript"],
            word_count_threshold=0,
            markdown_generator=DefaultMarkdownGenerator(
                options={"ignore_links": True, "ignore_images": True, "body_width": 0}
            ),
        )
        if css_selector:
            config_kwargs["css_selector"] = css_selector

        extraction_config = CrawlerRunConfig(**config_kwargs)

        target_url = "raw://" + self.raw_html

        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(
                url=target_url,
                config=extraction_config
            )

        soup = BeautifulSoup(self.raw_html, "html.parser")

        # Titolo dalla tag <title> (fallback)
        title_tag = soup.find("title")
        page_title = title_tag.text.strip() if title_tag else ""

        # Titolo articolo da h1.cover-title (più preciso, senza " | Yahoo Finance")
        cover_title_tag = soup.find("h1", class_=lambda c: c and "cover-title" in c)
        article_title = cover_title_tag.get_text(strip=True) if cover_title_tag else page_title

        raw_md = (result.markdown.raw_markdown if result.markdown else "") or ""

        if not raw_md.strip():
            return {"error": "Nessun testo estratto dall'HTML fornito."}

        return {
            "url": self.url,
            "domain": self.domain,
            "title": article_title,
            "html_text": self.raw_html,
            "parsed_text": self.clean_markdown(raw_md, page_type),
        }

    def clean_markdown(self, text: str, page_type: str = "") -> str:
        """Rimuove boilerplate e formattazione residua dall'output di Crawl4AI."""
        if not text:
            return ""

        # Sezioni rumore universali
        noise_sections = [
            "trending tickers", "recently viewed tickers",
            "you may also like", "related stories",
            "popular", "see also", "references",
        ]

        # Layer aggiuntivo per le quote: le news sono rumore
        if page_type == "quote":
            noise_sections += [
                "related news",
                "upcoming events",
                "recent events",
                "news",
            ]

        text = clean_markdown_by_sections(text, noise_sections)

        noise_indicators = [
            "data provided by", "all rights reserved", "sign in to",
            "try yahoo finance plus", "upgrade to premium",
            "cookie settings", "accept all", "privacy dashboard",
            "quotes are not sourced", "delayed at least",
            "disclaimer", "view more", "see more", "read more", "learn more",
            "expand all",
        ]
        text = clean_markdown_noise(text, noise_indicators)

        substitution_rules = [
            (r'!\[.*?\]\(.*?\)', ''),
            (r'\[([^\]]+)\]\(.*?\)', r'\1'),
            (r'https?://\S+', ''),
            # Residui byline: "Reuters April 7, 2026 1 min read" o "F -0.70% WASHINGTON..."
            (r'^[A-Z][A-Za-z\s]+\s+\w+\s+\d{1,2},\s+\d{4}\s+\d+\s+min\s+read\s*', ''),
            # Ticker residui tipo "F -0.70%" prima del testo
            (r'^[A-Z]{1,5}\s+[-+]?\d+\.\d+%\s*', ''),
            (r'[ \t]{2,}', ' '),
            (r'\n{3,}', '\n\n'),
        ]
        text = clean_markdown_regex(text, substitution_rules)

        return text.strip()

    @staticmethod
    def _remove_duplicate_paragraphs(text: str) -> str:
        blocks = re.split(r'\n{2,}', text)
        seen = []
        result = []

        for block in blocks:
            normalized = re.sub(r'\s+', ' ', block.strip().lower())
            if not normalized:
                continue

            is_duplicate = False
            for seen_block in seen:
                if normalized == seen_block:
                    is_duplicate = True
                    break
                shorter = min(normalized, seen_block, key=len)
                longer = max(normalized, seen_block, key=len)
                if len(shorter) > 100 and shorter in longer:
                    is_duplicate = True
                    break

            if not is_duplicate:
                seen.append(normalized)
                result.append(block)

        return '\n\n'.join(result)