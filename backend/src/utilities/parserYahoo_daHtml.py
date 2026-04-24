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
        elif "/news/" in self.url or "/m/" in self.url:
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

        if page_type == "quote":
            quote_specific = [
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
            ]
            return ", ".join(base + quote_specific)

        return ", ".join(base)

    def _build_css_selector(self, page_type: str) -> str | None:
        """
        Restringe l'estrazione al solo contenuto principale della pagina.
        Questo evita il problema del nav/header che su Yahoo contiene
        caratteri aria-hidden che crawl4ai strippa.
        """
        if page_type == "quote":
            return "#main-content-wrapper"
        return None

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
        title_tag = soup.find("title")
        title = title_tag.text.strip() if title_tag else ""

        raw_md = (result.markdown.raw_markdown if result.markdown else "") or ""

        if not raw_md.strip():
            return {"error": "Nessun testo estratto dall'HTML fornito."}

        return {
            "url": self.url,
            "domain": self.domain,
            "title": title,
            "html_text": self.raw_html,
            "parsed_text": self.clean_markdown(raw_md, page_type),
        }

    def clean_markdown(self, text: str, page_type: str = "generic") -> str:
        if not text:
            return ""

        # ── TAGLIO INIZIALE ──────────────────────────────────────────────────
        # Solo per pagine non-quote dove non usiamo css_selector.
        # Per le quote page il css_selector #main-content-wrapper
        # già esclude nav/header, quindi il taglio non serve.
        if page_type != "quote":
            match = re.search(r'(?m).*•.*', text)
            if match:
                text = text[match.start():]

        # ── SEZIONI RUMORE ───────────────────────────────────────────────────
        if page_type == "quote":
            noise_sections = [
                "trending tickers", "recently viewed tickers",
                "you may also like", "related news", "related stories",
                "popular", "see also", "references", "news about",
            ]
        else:
            noise_sections = [
                "trending tickers", "recently viewed tickers",
                "you may also like", "related stories",
                "popular", "see also",
            ]

        text = clean_markdown_by_sections(text, noise_sections)

        # ── INDICATORI RUMORE ────────────────────────────────────────────────
        noise_indicators = [
            "data provided by", "all rights reserved", "sign in to",
            "try yahoo finance plus", "upgrade to premium",
            "cookie settings", "accept all", "privacy dashboard",
            "quotes are not sourced", "delayed at least",
            "currency in", "disclaimer",
            "skip to navigation", "skip to main content",
            "powered by yahoo scout",
            "oops, something went wrong",
            "view more",
        ]
        text = clean_markdown_noise(text, noise_indicators)

        # ── REGEX DI PULIZIA ─────────────────────────────────────────────────
        substitution_rules = [
            (r'!\[.*?\]\(.*?\)', ''),
            (r'\[([^\]]+)\]\(.*?\)', r'\1'),
            (r'https?://\S+', ''),
            (r'(?m)^#{1,6}\s*[-+]?[\d.]+%\s*$', ''),
            (r'(?m)^#{1,6}\s*[\d,]+\.?\d*%?\s*$', ''),
            (r'[ \t]{2,}', ' '),
            (r'\n{3,}', '\n\n'),
        ]
        text = clean_markdown_regex(text, substitution_rules)

        # ── DEDUPLICAZIONE ───────────────────────────────────────────────────
        text = self._remove_duplicate_paragraphs(text)

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