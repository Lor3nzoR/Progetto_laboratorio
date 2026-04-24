from crawl4ai import CrawlerRunConfig, CacheMode
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

from .parserBase import ParserBase
from .md_cleaning import clean_markdown_by_sections, clean_markdown_noise, clean_markdown_regex


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
            css_selector="main, article, [role='main']",
            excluded_selector="""
                header, nav, footer, aside,
                .sf-top-header, .sf-header, .sf-footer,
                .sf-geo-navigation, .main-navigation, .top-header,
                .breadcrumb, .breadcrumbs,
                .social-share, .share, .language-selector,
                .translation-links, .donate, .newsletter,
                .slicknav_menu, .alphabetical-nav, .navigation,
                .region-picker, .sf-image-credit, .timestamp, .table-cell, .arrowed-link, 
                div.sf-publications-item__date, .titile, .arrowed-links, .section-heading, a.link, .section-navigation, .sidebar, .heading.text-underline
            """,
            excluded_tags=["style", "script", "nav", "footer", "aside", "form", "button", "svg"],
            word_count_threshold=0,
            markdown_generator=md_generator,
        )

    def clean_markdown(self, text: str) -> str:
        if not text:
            return ""

        # solo marker molto sicuri
        text = clean_markdown_by_sections(
            text,
            ["related", "related links"]
        )

        text = clean_markdown_noise(
            text,
            [
                "skip to main content",
                "select language",
                "health topics",
                "newsroom",
                "emergencies",
                "about who",
                "download",
                "read more",

            ]
        )

        text = clean_markdown_regex(
            text,
            [
                (r'!\[.*?\]\(.*?\)', ''),
                (r'\[([^\]]+)\]\(.*?\)', r'\1'),
                (r'[ \t]{2,}', ' '),
                (r'^\s*[=\-]{3,}\s*$', ''),
                (r'\s+([,.;:!?])', r'\1'),
                (r'(\d)\s+(st|nd|rd|th)\b', r'\1\2'),
                (r'\s*_\._\s*', '.'),
                (r'\n{3,}', '\n\n'),
            ]
        ).strip()

        lines = [line.strip() for line in text.splitlines()]

        # 1) rimuovi righe vuote multiple e boilerplate ovvio
        blacklist_exact = {
            "skip to main content",
            "select language",
            "world health organization",
            "related",
            "related links",
            "more",
            "learn more",
        }

        cleaned = []
        seen = set()
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

        # 2) tieni titolo + primo blocco narrativo continuo
        # tronca quando iniziano moduli secondari ricorrenti
        stop_markers = {
            "impact",
            "who teams",
            "related technical units",
            "resolutions and decisions",
            "other resources",
            "conditions",
            "diseases and conditions",
            "health and wellbeing",
            "substances",
            "health interventions",
            "human behaviour",
            "departmental update",
            "address",

            "emergency situation reports",
            "joint news release",
            "feature stories",
            "commentaries",
            "speeches",
            "statements",
            "technical documents",
            "events",
            "campaigns",
            "who occupied palestinian territory",
        }

        kept = []
        started_body = False

        for line in cleaned:
            low = line.lower().strip()

            if low in stop_markers:
                break

            if not started_body:
                kept.append(line)
                # appena entra vero testo, parte il body
                if line and not line.startswith("#"):
                    started_body = True
                continue

            kept.append(line)

        # 3) riattacca continuazioni spezzate:
        # se una riga successiva inizia minuscola o con connettivi,
        # probabilmente è la continuazione del paragrafo precedente
        merged = []
        join_starters = (
            "with ", "and ", "or ", "but ", "by ", "for ", "of ", "to ",
            "in ", "on ", "from ", "through ", "including ", "which ",
            "that ", "this ", "these ", "those ", "it ", "its "
        )

        for line in kept:
            if not line:
                if merged and merged[-1] != "":
                    merged.append("")
                continue

            if merged:
                prev = merged[-1]
                if (
                    prev
                    and prev != ""
                    and not prev.startswith("#")
                    and (
                        line[:1].islower()
                        or any(line.lower().startswith(s) for s in join_starters)
                    )
                ):
                    merged[-1] = prev.rstrip() + " " + line.lstrip()
                    continue

            merged.append(line)

        # 4) se non c'è un titolo markdown esplicito, lascia la prima riga come titolo semplice
        # niente # automatico: così resti più vicino ai GS che mi hai mostrato
        text = "\n".join(merged)
        text = clean_markdown_regex(text, [(r'\n{3,}', '\n\n')]).strip()

        return text
