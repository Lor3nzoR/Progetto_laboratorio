"""
Parser specializzato per who.int (World Health Organization).

Strategia di estrazione:
- CSS selector: main, article, [role='main']
  Il sito WHO usa strutture diverse a seconda della sezione; questo selettore
  copre i casi più comuni senza escludere contenuto utile.
- Esclusi: header, footer, navigazione, sidebar, widget di traduzione e donazione.
- Post-processing in 4 fasi:
  1. Rimozione sezioni/righe boilerplate.
  2. Deduplicazione paragrafi e filtraggio blacklist esatta.
  3. Troncamento al primo blocco narrativo (stop a sezioni secondarie ricorrenti).
  4. Ricongiungimento righe spezzate che iniziano con lettere minuscole o connettivi.
"""

from crawl4ai import CrawlerRunConfig, CacheMode
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

from .parserBase import ParserBase
from utilities.md_cleaning import clean_markdown_by_sections, clean_markdown_noise, clean_markdown_regex


class WHOParser(ParserBase):
    """Parser per pagine del sito who.int."""

    def set_crawler(self) -> CrawlerRunConfig:
        """
        Seleziona il contenuto principale ed esclude tutto il chrome del sito
        (navigazione globale, footer, banner, widget di condivisione).
        """
        return CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            css_selector="main, article, [role='main']",
            excluded_selector="""
                header, nav, footer, aside,
                .sf-top-header, .sf-header, .sf-footer,
                .sf-geo-navigation, .main-navigation, .top-header,
                .breadcrumb, .breadcrumbs,
                .social-share, .share, .language-selector,
                .translation-links, .donate, .newsletter,
                .slicknav_menu, .alphabetical-nav, .navigation,
                .region-picker, .sf-image-credit, .timestamp,
                .table-cell, .arrowed-link,
                div.sf-publications-item__date, .titile,
                .arrowed-links, .section-heading, a.link,
                .section-navigation, .sidebar, .heading.text-underline
            """,
            excluded_tags=["style", "script", "nav", "footer", "aside", "form", "button", "svg"],
            word_count_threshold=0,
            markdown_generator=DefaultMarkdownGenerator(
                options={"ignore_links": True, "ignore_images": True, "body_width": 0}
            ),
        )

    def clean_markdown(self, text: str) -> str:
        """
        Pulizia in 4 fasi progressive per ottenere solo il testo informativo
        della pagina, eliminando il boilerplate ricorrente del sito WHO.
        """
        if not text:
            return ""

        # Fase 1 – rimozione sezioni e righe boilerplate.
        text = clean_markdown_by_sections(text, ["related", "related links"])
        text = clean_markdown_noise(text, [
            "skip to main content", "select language",
            "health topics", "newsroom", "emergencies",
            "about who", "download", "read more",
        ])
        text = clean_markdown_regex(text, [
            (r"!\[.*?\]\(.*?\)",    ""),          # immagini markdown
            (r"\[([^\]]+)\]\(.*?\)", r"\1"),      # link → solo testo
            (r"[ \t]{2,}",          " "),          # spazi multipli
            (r"^\s*[=\-]{3,}\s*$",  ""),          # separatori orizzontali
            (r"\s+([,.;:!?])",      r"\1"),        # spazio prima di punteggiatura
            (r"(\d)\s+(st|nd|rd|th)\b", r"\1\2"), # ordinali: "1 st" → "1st"
            (r"\s*_\._\s*",         "."),          # artefatto " _._"
            (r"\n{3,}",             "\n\n"),       # righe vuote eccessive
        ]).strip()

        lines = [line.strip() for line in text.splitlines()]

        # Fase 2 – deduplicazione e blacklist esatta.
        blacklist_exact = {
            "skip to main content", "select language",
            "world health organization", "related",
            "related links", "more", "learn more",
        }
        cleaned = []
        seen: set[str] = set()
        for line in lines:
            if not line:
                if cleaned and cleaned[-1] != "":
                    cleaned.append("")
                continue
            low = line.lower()
            if low in blacklist_exact:
                continue
            sig = " ".join(low.split())
            if sig in seen:
                continue
            seen.add(sig)
            cleaned.append(line)

        # Fase 3 – troncamento al primo blocco narrativo.
        # Le sezioni secondarie del sito WHO hanno titoli ricorrenti e prevedibili;
        # interrompere qui evita di includere elenchi di risorse non pertinenti.
        stop_markers = {
            "impact", "who teams", "related technical units",
            "resolutions and decisions", "other resources",
            "conditions", "diseases and conditions",
            "health and wellbeing", "substances",
            "health interventions", "human behaviour",
            "departmental update", "address",
            "emergency situation reports", "joint news release",
            "feature stories", "commentaries", "speeches",
            "statements", "technical documents", "events",
            "campaigns", "who occupied palestinian territory",
        }
        kept = []
        started_body = False
        for line in cleaned:
            if line.lower().strip() in stop_markers:
                break
            if not started_body:
                kept.append(line)
                if line and not line.startswith("#"):
                    started_body = True
                continue
            kept.append(line)

        # Fase 4 – ricongiungimento righe spezzate.
        # Una riga che inizia con minuscola o con un connettivo inglese
        # è quasi sempre la continuazione del paragrafo precedente.
        join_starters = (
            "with ", "and ", "or ", "but ", "by ", "for ", "of ", "to ",
            "in ", "on ", "from ", "through ", "including ", "which ",
            "that ", "this ", "these ", "those ", "it ", "its ",
        )
        merged = []
        for line in kept:
            if not line:
                if merged and merged[-1] != "":
                    merged.append("")
                continue
            if merged:
                prev = merged[-1]
                if (
                    prev and prev != "" and not prev.startswith("#")
                    and (
                        line[:1].islower()
                        or any(line.lower().startswith(s) for s in join_starters)
                    )
                ):
                    merged[-1] = prev.rstrip() + " " + line.lstrip()
                    continue
            merged.append(line)

        text = "\n".join(merged)
        text = clean_markdown_regex(text, [(r"\n{3,}", "\n\n")]).strip()
        return text
