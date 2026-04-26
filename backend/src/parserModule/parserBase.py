"""
Classe base astratta per tutti i parser del progetto.

Ogni parser di dominio estende ParserBase e deve implementare:
  - set_crawler()   → configurazione specifica di Crawl4AI per il dominio
  - clean_markdown() → pulizia del markdown prodotto da Crawl4AI

Il flusso principale è:
  get_data()      → scarica l'HTML dall'URL e delega a parse_html()
  parse_html()    → riceve HTML già disponibile, lo processa con Crawl4AI
                    e applica clean_markdown()
"""

from abc import ABC, abstractmethod
from pathlib import Path
from urllib.parse import urlparse

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator


class ParserBase(ABC):
    """
    Classe base astratta per i parser di dominio.

    Il costruttore riceve l'URL completo della pagina da parsare e
    inizializza le configurazioni di crawler e browser attraverso
    i metodi astratti set_crawler() e set_browser().
    """

    def __init__(self, url: str):
        self.url: str = url
        self.domain: str = urlparse(url).netloc
        self.crawl_config: CrawlerRunConfig = self.set_crawler()
        self.browser_config: BrowserConfig = self.set_browser()

    async def get_data(self) -> dict:
        """
        Scarica l'HTML dall'URL, lo salva in un file temporaneo e poi
        delega l'intera elaborazione a parse_html().
        Questo metodo è il punto di ingresso per GET /parse.
        """
        file_path = await self.get_raw_html()
        html_grezzo = Path(file_path).read_text(encoding="utf-8")
        return await self.parse_html(html_grezzo)

    async def parse_html(self, html_text: str, title_override: str = "", crawler: AsyncWebCrawler | None = None) -> dict:
        """
        Parsifica una stringa HTML già disponibile usando Crawl4AI.
        Questo metodo è il punto di ingresso per POST /parse e full_gs_eval.

        Se la configurazione specifica del parser non produce testo, viene
        applicata una configurazione di fallback generica per evitare
        di restituire risultati vuoti.
        """
        fallback_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            excluded_tags=["script", "style", "nav", "footer", "noscript"],
            word_count_threshold=0,
            markdown_generator=DefaultMarkdownGenerator(
                options={"ignore_links": True, "ignore_images": True, "body_width": 0}
            )
        )

        async def run_parse(active_crawler: AsyncWebCrawler) -> dict:
            result = await active_crawler.arun(url=f"raw:{html_text}", config=self.crawl_config)

            if not result.success:
                return {"error": "Crawl4AI non è riuscito a processare l'HTML."}

            raw_markdown = result.markdown.raw_markdown or ""

            # Se la configurazione specifica non ha prodotto testo, si usa il fallback.
            if not raw_markdown.strip():
                result = await active_crawler.arun(url=f"raw:{html_text}", config=fallback_config)

                if not result.success:
                    return {"error": "Fallback Crawl4AI fallito."}

                raw_markdown = result.markdown.raw_markdown or ""

            cleaned_text = self.clean_markdown(raw_markdown)

            return {
                "url": self.url,
                "domain": self.domain,
                "title": title_override or result.metadata.get("title", ""),
                "html_text": html_text,
                "parsed_text": cleaned_text,
            }

        if crawler is None:
            async with AsyncWebCrawler(config=self.browser_config) as managed_crawler:
                return await run_parse(managed_crawler)

        return await run_parse(crawler)

    async def get_raw_html(self) -> str:
        """
        Scarica l'HTML grezzo dall'URL e lo salva in backend/data/cache.html.
        Restituisce il percorso assoluto del file salvato.
        """
        # __file__ → backend/src/utilities/parserBase.py → parents[2] → backend/
        backend_root = Path(__file__).resolve().parents[2]
        data_dir = backend_root / "data"
        data_dir.mkdir(exist_ok=True)

        cache_path = str(data_dir / "cache.html")

        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(url=self.url)
            with open(cache_path, "w", encoding="utf-8") as f:
                f.write(result.html)

        return cache_path

    @abstractmethod
    def set_crawler(self) -> CrawlerRunConfig:
        """
        Configura il CrawlerRunConfig specifico per il dominio.
        Ogni parser di dominio definisce qui i CSS selector, i tag da escludere
        e le opzioni del generatore di markdown.
        """
        pass

    def set_browser(self) -> BrowserConfig:
        """
        Configurazione di default del browser Chromium headless.
        I parser che necessitano di impostazioni particolari (es. user-agent
        personalizzato) possono sovrascrivere questo metodo.
        """
        return BrowserConfig(headless=True, browser_type="chromium")

    @abstractmethod
    def clean_markdown(self, markdown_output: str) -> str:
        """
        Applica la pulizia specifica del dominio al markdown grezzo prodotto da Crawl4AI.
        Ogni parser implementa qui la rimozione di boilerplate, rumore e
        formattazione residua tipica del sito.
        """
        pass

