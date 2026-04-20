<<<<<<< HEAD
=======
import os
>>>>>>> a6cf71b (Commit iniziale)
from pathlib import Path
from abc import ABC, abstractmethod
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
from urllib.parse import urlparse
<<<<<<< HEAD
=======
from uuid import uuid4
>>>>>>> a6cf71b (Commit iniziale)

class ParserBase(ABC):

    def __init__(self, url):
        self.url : str = url #url completo
        self.domain : str = urlparse(url).netloc #dominio che servirà in output
        self.crawl_config = self.set_crawler() #configurazione del crawler
        self.browser_config = self.set_browser() #configurazione del browser

<<<<<<< HEAD
    async def get_data(self) -> dict:
        """
        Questo è lo schema base per l'estrazione dei dati da una pagina web
        e relativo output strutturato, può variare in base all'implementazione specifica
        delle funzioni di configurazione del crawler e pulizia del markdown
        """
        #come primo step recuperiamo il percorso del raw_html
        file_path = await self.get_raw_html()
        #lo convertiamo nell'uri da passare al crawler
        local_html = f"file://{file_path}"

        async with AsyncWebCrawler(config=self.browser_config) as crawler:
            # Eseguiamo il crawler e filtriamo l'html grezzo
            result = await crawler.arun(url=local_html, config=self.crawl_config)
            
            if not result.success:
                return {"error": "Failed to crawl"}

            # Puliamo il testo usando la funzione di pulizia per il markdown
            cleaned_text = self.clean_markdown(result.markdown.raw_markdown) 

            # Recuriamo il contenuto del raw html per restituirlo in output
            html_grezzo = Path(file_path).read_text(encoding="utf-8")

            # Restituiamo esattamente la struttura richiesta dall'esonero
            return {
                "url": self.url,
                "domain": self.domain,
                "title": result.metadata.get('title', ''),
                "html_text": html_grezzo,           # HTML grezzo
                "parsed_text": cleaned_text         # Markdown pulito
            }
=======
    @abstractmethod
    async def get_data(self) -> dict:
        """
        metodo per restituire in output i dati parsati nel formato richiesto
        """
        pass
>>>>>>> a6cf71b (Commit iniziale)

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

<<<<<<< HEAD
=======
    # ===== INIZIO CODICE SCRITTO DA CODEX =====
    def _get_backend_root(self) -> Path:
        """
        Restituisce il path assoluto della cartella backend.
        """
        return Path(__file__).resolve().parents[2]

    def _get_data_dir(self) -> Path:
        """
        Restituisce la cartella usata per i file HTML temporanei del parser.
        """
        data_dir = self._get_backend_root() / "data"
        data_dir.mkdir(exist_ok=True)
        return data_dir

    def save_html_text(self, html_text: str) -> Path:
        """
        Salva un HTML grezzo su file per permettere il parsing locale tramite
        Crawl4AI.
        """
        file_path = self._get_data_dir() / f"cache_{uuid4().hex}.html"
        file_path.write_text(html_text, encoding="utf-8")
        return file_path

    async def build_data_from_html_file(
        self,
        file_path: str | Path,
        title_override: str = ""
    ) -> dict:
        """
        Esegue il parsing a partire da un file HTML locale e restituisce la
        struttura JSON richiesta dalla consegna.
        """
        local_html = f"file://{Path(file_path).resolve()}"

        async with AsyncWebCrawler(config=self.browser_config) as crawler:
            result = await crawler.arun(url=local_html, config=self.crawl_config)

            if not result.success:
                return {"error": "Failed to crawl"}

            cleaned_text = self.clean_markdown(result.markdown.raw_markdown)
            html_grezzo = Path(file_path).read_text(encoding="utf-8")

            return {
                "url": self.url,
                "domain": self.domain,
                "title": title_override or result.metadata.get("title", ""),
                "html_text": html_grezzo,
                "parsed_text": cleaned_text
            }
    # ===== FINE CODICE SCRITTO DA CODEX =====

>>>>>>> a6cf71b (Commit iniziale)
        
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
<<<<<<< HEAD
        pass
=======
        pass
>>>>>>> a6cf71b (Commit iniziale)
