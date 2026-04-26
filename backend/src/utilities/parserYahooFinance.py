"""
Parser specializzato per finance.yahoo.com.

Strategia di estrazione:
- Rilevamento tipo pagina: quote, article, markets o generic.
  Ogni tipologia richiede selettori, attese e filtri diversi.
- Gestione consenso GDPR: una sessione requests raccoglie i cookie dal flusso
  GUCE, poi Crawl4AI carica la pagina reale con quello stato gia impostato.
- Post-processing: rimozione di widget finanziari, moduli video, byline,
  ticker residui e boilerplate promozionale.

Nota: la complessita principale di questo parser non e il cleanup finale,
ma l'aggiramento affidabile del muro di consenso europeo.
"""

import re

import requests
from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode, BrowserConfig
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

from .parserBase import ParserBase
from .md_cleaning import clean_markdown_by_section_title, clean_markdown_by_sections, clean_markdown_noise, clean_markdown_regex


class ParserYahooFinance(ParserBase):
    """
    Parser per pagine del dominio finance.yahoo.com.

    Supporta sia pagine articolo sia pagine quotazione/mercato, che hanno
    layout e rumore molto diversi tra loro.
    """

    _REQUEST_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
    }

    def set_crawler(self) -> CrawlerRunConfig:
        """Config di base vuota: la configurazione effettiva dipende dalla pagina."""
        return CrawlerRunConfig()

    def set_browser(self) -> BrowserConfig:
        """Browser con user-agent desktop reale per ridurre il rilevamento bot."""
        return BrowserConfig(
            headless=True,
            browser_type="chromium",
            user_agent=self._REQUEST_HEADERS["User-Agent"],
            extra_args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--window-size=1920,1080",
            ],
            headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": self._REQUEST_HEADERS["Accept"],
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            },
        )

    def _get_page_type(self) -> str:
        """Classifica l'URL per scegliere selettori, attese e pulizia dedicate."""
        if "/quote/" in self.url:
            return "quote"
        elif any(p in self.url for p in ["/news/", "/m/", "/article/", "/story/"]):
            return "article"
        elif "/markets/" in self.url:
            return "markets"
        return "generic"

    def _build_excluded_selector(self, page_type: str) -> str:
        """
        Costruisce la blacklist CSS combinando rumore comune del sito
        e widget specifici per il tipo di pagina.
        """
        base = [
            "footer",
            "nav",
            "aside",
            "header.hideOnPrint",
            "header._yb_p560ks",
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
            "[data-testid='video-player']",
            "[data-testid='related-video-player']",
            ".video-module",
            ".js-stream-content",
            "[data-testid='ticker-news']",
        ]

        article_extra = [
            "header",
            "[data-testid='sidebar']",
            "[data-testid='related-articles']",
            "[data-testid='author-bio']",
            ".caas-readmore",
            ".caas-more-content",
            ".recommendations",
            "figcaption",
            ".byline",
            ".ticker-list",
            ".readmore",
            ".article-footer",
            ".cover-slideshow-wrapper",
        ]

        if page_type == "quote":
            return ", ".join(base + quote_extra)
        elif page_type == "article":
            return ", ".join(base + article_extra)

        return ", ".join(base)

    def _build_css_selector(self, page_type: str) -> str | None:
        """Seleziona il contenitore principale piu adatto al layout rilevato."""
        if page_type == "quote":
            return "main"
        elif page_type == "article":
            return "[data-testid='article-body'], .caas-body"
        return "#main-content-wrapper"

    def _build_js_cleanup(self, page_type: str) -> str | None:
        """Rimuove client-side widget che spesso sfuggono ai soli selettori CSS."""
        if page_type == "article":
            return """
                document.querySelectorAll('li[data-testid^="seamlessscroll-"]')
                        .forEach(el => el.remove());
                document.querySelectorAll('figcaption, .byline, .ticker-list, .readmore, .article-footer')
                        .forEach(el => el.remove());
            """
        if page_type == "quote":
            return """
                document.querySelectorAll(
                    '[data-testid="video-player"], [data-testid="related-video-player"], ' +
                    '.video-module, .js-stream-content, [data-testid="ticker-news"], ' +
                    '[data-testid="ticker-news-summary"], [data-testid="recent-news"], ' +
                    '.watch-now-lead'
                ).forEach(el => el.remove());
            """
        return None

    def _get_consent_cookies(self) -> list[dict]:
        """
        Usa requests per:
        1. Seguire il redirect da finance.yahoo.com a guce.yahoo.com
        2. Estrarre i campi nascosti del form di consenso GDPR
        3. Fare il POST con agree=agree
        4. Restituire i cookie nel formato atteso da Crawl4AI.
        """
        session = requests.Session()
        session.headers.update(self._REQUEST_HEADERS)

        try:
            resp = session.get(self.url, timeout=30)
        except requests.RequestException as e:
            raise RuntimeError(f"[YahooFinance] Errore GET {self.url}: {e}") from e

        is_consent_page = (
            "Le tue scelte relative alla privacy" in resp.text
            or "consent-page" in resp.text
            or "guce.yahoo.com" in resp.url
        )

        if is_consent_page:
            fields = {
                "csrfToken": re.search(r'name="csrfToken"\s+value="([^"]+)"', resp.text),
                "sessionId": re.search(r'name="sessionId"\s+value="([^"]+)"', resp.text),
                "namespace": re.search(r'name="namespace"\s+value="([^"]+)"', resp.text),
                "originalDoneUrl": re.search(
                    r'name="originalDoneUrl"\s+value="([^"]+)"', resp.text
                ),
            }

            if not fields["csrfToken"] or not fields["sessionId"]:
                return self._session_cookies_to_list(session)

            form_data = {
                key: match.group(1)
                for key, match in fields.items()
                if match
            }
            form_data["agree"] = "agree"

            try:
                session.post(resp.url, data=form_data, timeout=30)
            except requests.RequestException:
                pass

        return self._session_cookies_to_list(session)

    @staticmethod
    def _session_cookies_to_list(session: requests.Session) -> list[dict]:
        """Converte i cookie di una sessione requests nel formato di Crawl4AI."""
        return [
            {
                "name": cookie.name,
                "value": cookie.value,
                "domain": cookie.domain or ".yahoo.com",
                "path": cookie.path or "/",
            }
            for cookie in session.cookies
        ]

    async def get_data(self) -> dict:
        """
        Scarica e parsa la pagina Yahoo Finance in due fasi:
        1. _get_consent_cookies() gestisce il consenso GDPR via requests
        2. Crawl4AI carica la pagina con i cookie gia impostati.
        """
        try:
            consent_cookies = self._get_consent_cookies()
        except RuntimeError as e:
            return {"error": str(e)}

        page_type = self._get_page_type()
        css_selector = self._build_css_selector(page_type)

        browser_with_cookies = BrowserConfig(
            headless=True,
            browser_type="chromium",
            user_agent=self._REQUEST_HEADERS["User-Agent"],
            extra_args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--window-size=1920,1080",
            ],
            headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": self._REQUEST_HEADERS["Accept"],
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            },
            storage_state={"cookies": consent_cookies, "origins": []},
        )

        config_kwargs = dict(
            cache_mode=CacheMode.BYPASS,
            wait_until="domcontentloaded",
            delay_before_return_html=12.0,
            page_timeout=60000,
            excluded_selector=self._build_excluded_selector(page_type),
            excluded_tags=["script", "style", "iframe", "noscript"],
            word_count_threshold=0,
            markdown_generator=DefaultMarkdownGenerator(
                options={"ignore_links": True, "ignore_images": True, "body_width": 0, "ignore_tables": True}
            ),
        )

        if css_selector:
            config_kwargs["css_selector"] = css_selector

        js_cleanup = self._build_js_cleanup(page_type)
        if js_cleanup:
            config_kwargs["js_code"] = js_cleanup

        # Ogni layout espone il contenuto utile con tempi diversi:
        # aspettiamo un segnale concreto solo dove serve.
        if page_type == "markets":
            config_kwargs["wait_for"] = "css:table td:not(:empty)"
        elif page_type == "article":
            config_kwargs["wait_for"] = "css:[data-testid='article-body']"

        live_config = CrawlerRunConfig(**config_kwargs)

        async with AsyncWebCrawler(config=browser_with_cookies) as crawler:
            result = await crawler.arun(url=self.url, config=live_config)

        html = result.html or ""
        raw_md = (result.markdown.raw_markdown if result.markdown else "") or ""
        if not html:
            return {"error": "Nessun HTML ricevuto dalla pagina."}

        if "Le tue scelte relative alla privacy" in html or "consent-page" in html:
            return {"error": "Bloccato dalla pagina di consenso GDPR nonostante i cookie."}

        if not raw_md.strip():
            return {"error": "Nessun testo estratto dalla pagina."}

        soup = BeautifulSoup(html, "html.parser")
        page_title = result.metadata.get("title", "") if result.metadata else ""
        cover_title_tag = soup.find("h1", class_=lambda c: c and "cover-title" in c)
        article_title = cover_title_tag.get_text(strip=True) if cover_title_tag else page_title

        return {
            "url": self.url,
            "domain": getattr(self, 'domain', 'finance.yahoo.com'),
            "title": article_title,
            "html_text": html,
            "parsed_text": self.clean_markdown(raw_md, page_type),
        }

    def clean_markdown(self, text: str, page_type: str = "") -> str:
        """
        Pulizia progressiva dell'output di Crawl4AI:
        1. Rimozione di sezioni intere di video, news correlate e widget.
        2. Filtro di righe con boilerplate commerciale o tecnico.
        3. Pulizia regex di link, byline, ticker e separatori residui.
        """
        if not text:
            return ""

        noise_sections = [
            "trending tickers", "recently viewed tickers",
            "you may also like", "related stories",
            "popular", "see also", "references",
        ]

        if page_type == "quote":
            noise_sections += [
                "related news",
                "upcoming events",
                "recent events",
                "news",
            ]

        text = clean_markdown_by_sections(text, noise_sections)

        text = clean_markdown_by_section_title(text, titles_to_remove=["related videos", "related news", "yahoo finance video", "recent news"])

        noise_indicators = [
            "data provided by", "all rights reserved", "sign in to",
            "try yahoo finance plus", "upgrade to premium",
            "cookie settings", "accept all", "privacy dashboard",
            "quotes are not sourced", "delayed at least",
            "disclaimer", "view more", "see more", "read more", "learn more",
            "expand all", "view original content to download multimedia",
            "newsroom: media hub",
            "all sectors",
            "select a sector for",
            "note: percentage % data",
            "valuation by forge",
            "firm data by equityzen",
            "powered by polymarket",
            "videos cannot play",
            "yahoo finance video",
            "error code:",
            "session id:",
        ]
        text = clean_markdown_noise(text, noise_indicators)

        substitution_rules = [
            (r'!\[.*?\]\(.*?\)', ''),
            (r'\[([^\]]+)\]\(.*?\)', r'\1'),
            (r'https?://\S+', ''),
            (r'(?i)^(view original content|more information about|for more information).*$', ''),
            # Residui di byline editoriale tipici degli articoli Yahoo/Reuters.
            (r'^[A-Z][A-Za-z\s]+\s+\w+\s+\d{1,2},\s+\d{4}\s+\d+\s+min\s+read\s*', ''),
            # Ticker residui in testa al paragrafo, tipici dei box finanziari.
            (r'^[A-Z]{1,5}\s+[-+]?\d+\.\d+%\s*', ''),
            # Scale numeriche/heatmap che compaiono nelle pagine mercati.
            (r'(?m)^<=?\s*-?\d[\d\s\->=]*$', ''),
            (r'[ \t]{2,}', ' '),
            (r'\n{3,}', '\n\n'),
            (r'(?m)^###[^\n]+\nYahoo Finance Video[^\n]*\n', ''),
        ]
        text = clean_markdown_regex(text, substitution_rules)

        return text.strip()

    @staticmethod
    def _remove_duplicate_paragraphs(text: str) -> str:
        """
        Deduplica blocchi quasi identici.
        Utile come fallback per layout che ripetono teaser e corpo articolo.
        """
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
