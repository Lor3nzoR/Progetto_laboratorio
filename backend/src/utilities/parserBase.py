from pathlib import Path
from abc import ABC, abstractmethod
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from urllib.parse import urlparse

class ParserBase(ABC):

    def __init__(self, url):
        self.url : str = url #url completo
        self.domain : str = urlparse(url).netloc #dominio che servirà in output
        self.crawl_config = self.set_crawler() #configurazione del crawler
        self.browser_config = self.set_browser() #configurazione del browser

    async def get_data(self) -> dict:
        """
        Questo è lo schema base per l'estrazione dei dati da una pagina web
        e relativo output strutturato, può variare in base all'implementazione specifica
        delle funzioni di configurazione del crawler e pulizia del markdown
        """
        # MODIFICA: il recupero dell'HTML da URL resta qui, ma il parsing vero
        # e proprio viene delegato a parse_html(), cosi' tutti i parser espongono
        # la stessa interfaccia e il server non deve distinguere casi speciali.
        #come primo step recuperiamo il percorso del raw_html
        file_path = await self.get_raw_html()
        html_grezzo = Path(file_path).read_text(encoding="utf-8")
        return await self.parse_html(html_grezzo)

    async def parse_html(self, html_text: str, title_override: str = "") -> dict:
        """
        MODIFICA: punto di ingresso comune per parsare una stringa HTML gia'
        disponibile. Il server puo' riusare sempre questa API.
        """
        fallback_markdown_generator = DefaultMarkdownGenerator(
            options={
                "ignore_links": True,
                "ignore_images": True,
                "body_width": 0
            }
        )

        fallback_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            excluded_tags=["script", "style", "nav", "footer", "noscript"],
            word_count_threshold=0,
            markdown_generator=fallback_markdown_generator
        )

        async with AsyncWebCrawler(config=self.browser_config) as crawler:
            result = await crawler.arun(
                url=f"raw:{html_text}",
                config=self.crawl_config
            )

            if not result.success:
                return {"error": "Failed to crawl"}

            raw_markdown = result.markdown.raw_markdown or ""

            # MODIFICA: fallback comune per tutti i parser che si basano su Crawl4AI.
            if not raw_markdown.strip():
                result = await crawler.arun(
                    url=f"raw:{html_text}",
                    config=fallback_config
                )

                if not result.success:
                    return {"error": "Failed to crawl"}

                raw_markdown = result.markdown.raw_markdown or ""

        cleaned_text = self.clean_markdown(raw_markdown)

        return {
            "url": self.url,
            "domain": self.domain,
            "title": title_override or result.metadata.get('title', ''),
            "html_text": html_text,
            "parsed_text": cleaned_text
        }

    async def get_raw_html(self) -> str:
        """
        metodo per recuperare il raw html dalla pagina e salvarlo
        localmente su un file che verrà poi utilizzato per il parsing effettivo,
        restituisce il percorso assoluto del file
        """
        
        #troviamo la radice del backend (rispetto a questo file)
        # __file__ è "backend/src/utilities/parserBase.py"
        # .parent è "backend/src/utilities/"
        # .parents[1] è "backend/src/"
        # .parents[2] è "backend/" (la nostra cartella base nel container)
        BACKEND_ROOT = Path(__file__).resolve().parents[2]

        #definiamo il path della cartella dati
        DATA_DIR = BACKEND_ROOT / "data"

        #assicuriamoci che esista (utile al primo avvio)
        DATA_DIR.mkdir(exist_ok=True)

        #costruiamo il percorso assoluto del file su cui salvare l'html
        percorso_file : str = f"{DATA_DIR}/cache.html"


        #eseguiamo il crawler per l'html grezzo e salviamo sul file
        #nota: in questo caso sia il browserConfig che il CrawlerConfig 
        #hanno le impostazioni di default
        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(url=self.url)
            with open(percorso_file, "w", encoding="utf-8") as f:
                f.write(result.html)
        
        print("Html grezzo estratto con successo!\n")

        return percorso_file

        
    @abstractmethod
    def set_crawler(self) -> CrawlerRunConfig:
        """
        metodo per configurare il crawler in modo specifico per ogni parser
        al fine di escludere deglielementi dall'html già in fase di estrazione
        """
        pass

    def set_browser(self) -> BrowserConfig:
        """
        metodo uguale per tutti i parser per settare le configurazioni di browser.
        Possiamo sovrascriverlo in modo più specifico all'occorrenza
        """
        return BrowserConfig(
            # Headless: True per i server, False se si vuole vedere cosa succede
            headless=True,
        
            # lasciamo il valore di default
            browser_type="chromium",
    )

    @abstractmethod
    def clean_markdown(self, markdown_output : str):
        """
        metodo per ripulire il markdown restituito da Crawl4ai in base al dominio specifico 
        tramite regex ed eventuali altre manipolazioni
        """
        pass
