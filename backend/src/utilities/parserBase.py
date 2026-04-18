import os
from pathlib import Path
from abc import ABC, abstractmethod
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
from urllib.parse import urlparse

class ParserBase(ABC):

    def __init__(self, url):
        self.url : str = url #url completo
        self.domain : str = urlparse(url).netloc #dominio che servirà in output
        self.crawl_config = self.set_crawler() #configurazione del crawler
        self.browser_config = self.set_browser() #configurazione del browser

    @abstractmethod
    async def get_data(self) -> dict:
        """
        metodo per restituire in output i dati parsati nel formato richiesto
        """
        pass

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