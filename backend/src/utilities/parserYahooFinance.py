# backend/src/utilities/parserYahooFinance.py

import re
import requests
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode, BrowserConfig
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from .parserBase import ParserBase
from .md_cleaning import clean_markdown_by_sections, clean_markdown_noise, clean_markdown_regex


class ParserYahooFinance(ParserBase):
    """
    Parser specifico per finance.yahoo.com.

    Yahoo Finance in area UE mostra prima una pagina di consenso GDPR
    su guce.yahoo.com. Il click del bottone causa una navigazione cross-domain
    (guce → finance) che Crawl4AI non gestisce correttamente.

    Soluzione in due fasi:
    1. requests (sincrono) segue il redirect al consenso, estrae il form,
       fa il POST e raccoglie i cookie di consenso impostati dal server.
    2. Crawl4AI carica la pagina reale con quei cookie già presenti nel
       browser, bypassando completamente il muro del consenso.
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
        """
        Configurazione usata dal POST /parse (HTML già disponibile, no JS).
        """
        return CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            excluded_selector=", ".join([
                "header", "footer", "nav", "aside",
                "[class*='ad']", "[id*='ad']",
            ]),
            excluded_tags=["script", "style", "iframe", "noscript"],
            word_count_threshold=0,
            markdown_generator=DefaultMarkdownGenerator(
                options={"ignore_links": True, "ignore_images": True, "body_width": 0}
            ),
        )

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

    def _get_consent_cookies(self) -> list[dict]:
        """
        Usa requests per:
        1. Seguire il redirect da finance.yahoo.com a guce.yahoo.com
        2. Estrarre i campi nascosti del form di consenso GDPR
        3. Fare il POST con agree=agree
        4. Restituire i cookie nel formato atteso da Crawl4AI

        Se non c'è pagina di consenso (cookie già presenti o altro),
        restituisce i cookie della sessione corrente.
        """
        session = requests.Session()
        session.headers.update(self._REQUEST_HEADERS)

        try:
            resp = session.get(self.url, timeout=30)
        except requests.RequestException as e:
            raise RuntimeError(f"[YahooFinance] Errore GET {self.url}: {e}") from e

        # Controlla se siamo sulla pagina di consenso
        is_consent_page = (
            "Le tue scelte relative alla privacy" in resp.text
            or "consent-page" in resp.text
            or "guce.yahoo.com" in resp.url
        )

        if is_consent_page:
            # Estrae i campi nascosti del form con regex
            fields = {
                "csrfToken": re.search(r'name="csrfToken"\s+value="([^"]+)"', resp.text),
                "sessionId": re.search(r'name="sessionId"\s+value="([^"]+)"', resp.text),
                "namespace": re.search(r'name="namespace"\s+value="([^"]+)"', resp.text),
                "originalDoneUrl": re.search(
                    r'name="originalDoneUrl"\s+value="([^"]+)"', resp.text
                ),
            }

            if not fields["csrfToken"] or not fields["sessionId"]:
                # Form non trovato: restituisce i cookie esistenti
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
                pass  # Anche se il POST fallisce, i cookie parziali possono bastare

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
        2. Crawl4AI carica la pagina con i cookie già impostati
        """
        # Fase 1: ottieni i cookie di consenso
        try:
            consent_cookies = self._get_consent_cookies()
        except RuntimeError as e:
            return {"error": str(e)}

        # Fase 2: carica la pagina reale con i cookie iniettati nel browser.
        # I cookie vanno in BrowserConfig.storage_state (formato Playwright):
        # CrawlerRunConfig non supporta il parametro cookies in questa versione.
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

        live_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            wait_until="domcontentloaded",
            delay_before_return_html=5.0,
            excluded_selector=", ".join([
                "header", "footer", "nav", "aside",
                "[class*='ad']", "[id*='ad']",
                ".consent-overlay", "#consent-page",
            ]),
            excluded_tags=["script", "style", "iframe", "noscript"],
            word_count_threshold=0,
            page_timeout=45000,
            markdown_generator=DefaultMarkdownGenerator(
                options={"ignore_links": True, "ignore_images": True, "body_width": 0}
            ),
        )

        async with AsyncWebCrawler(config=browser_with_cookies) as crawler:
            result = await crawler.arun(url=self.url, config=live_config)

        html = result.html or ""
        raw_md = (result.markdown.raw_markdown if result.markdown else "") or ""

        if not html:
            return {"error": "Nessun HTML ricevuto dalla pagina."}

        # Verifica che non siamo ancora sulla pagina di consenso
        if "Le tue scelte relative alla privacy" in html or "consent-page" in html:
            return {"error": "Bloccato dalla pagina di consenso GDPR nonostante i cookie."}

        if not raw_md.strip():
            return {"error": "Nessun testo estratto dalla pagina."}

        return {
            "url": self.url,
            "domain": self.domain,
            "title": result.metadata.get("title", "") if result.metadata else "",
            "html_text": html,
            "parsed_text": self.clean_markdown(raw_md),
        }

    def clean_markdown(self, text: str) -> str:
        """Rimuove boilerplate e formattazione residua dall'output di Crawl4AI."""
        if not text:
            return ""

        noise_sections = [
            "trending tickers", "recently viewed tickers",
            "you may also like", "related news", "related stories",
            "popular", "see also", "references",
        ]
        text = clean_markdown_by_sections(text, noise_sections)

        noise_indicators = [
            "data provided by", "all rights reserved", "sign in to",
            "try yahoo finance plus", "upgrade to premium",
            "cookie settings", "accept all", "privacy dashboard",
            "quotes are not sourced", "delayed at least",
            "currency in", "disclaimer",
        ]
        text = clean_markdown_noise(text, noise_indicators)

        substitution_rules = [
            (r'!\[.*?\]\(.*?\)', ''),           # rimuove immagini markdown
            (r'\[([^\]]+)\]\(.*?\)', r'\1'),    # link -> solo testo
            (r'https?://\S+', ''),              # URL solitari
            (r'[ \t]{2,}', ' '),                # spazi multipli
            (r'\n{3,}', '\n\n'),                # righe vuote eccessive
        ]
        text = clean_markdown_regex(text, substitution_rules)

        return text.strip()