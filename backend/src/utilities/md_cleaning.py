"""
Primitive di pulizia markdown riutilizzate dai parser di dominio.

Il modulo fornisce helper progressivi:
- rimozione di sezioni intere tramite blacklist di titoli;
- filtraggio di righe rumorose tramite indicatori testuali;
- sostituzioni regex parametrizzabili;
- rimozione di blocchi identificati da un titolo markdown specifico.
"""

import re
from typing import Iterable


def clean_markdown_by_sections(raw_markdown: str, sections_to_remove: Iterable[str]) -> str:
    """
    Rimuove intere sezioni markdown di livello `##` in base al titolo.
    Mantiene l'introduzione iniziale e ricostruisce solo i blocchi ammessi.
    """
    # Ripulisce gli escape piu comuni lasciati dal renderer markdown.
    text = raw_markdown.replace('\\"', '"').replace('\\.', '.').replace('\\!', '!')

    # Il parsing e volutamente semplice: i parser del progetto producono
    # heading second-level abbastanza regolari da poterli trattare via split.
    sections = re.split(r'\n##\s+', text)

    # La prima cella contiene sempre il testo precedente al primo heading.
    clean_parts = []
    intro = sections[0].strip()
    if intro:
        clean_parts.append(intro)

    # Pre-normalizza la blacklist per confronti case-insensitive.
    blacklist = [s.lower().strip() for s in sections_to_remove]

    for section in sections[1:]:
        # Il primo newline separa titolo e corpo della sezione.
        lines = section.split('\n', 1)
        if len(lines) < 2:
            continue

        title = lines[0].strip()
        content = lines[1].strip()

        if title.lower() not in blacklist:
            clean_parts.append(f"\n## {title}\n{content}")

    return "\n\n".join(clean_parts)


def clean_markdown_noise(raw_markdown: str, noise_indicators: Iterable[str]) -> str:
    """
    Rimuove righe di rumore, avvisi e righe vuote da un testo markdown.
    Il filtro e per sottostringa, quindi cattura anche varianti dello stesso boilerplate.
    """
    lines = raw_markdown.split('\n')
    cleaned_lines = []

    # Normalizza una sola volta gli indicatori per evitare lavoro ripetuto nel loop.
    noise_list = [str(ind).strip().lower() for ind in noise_indicators]

    for line in lines:
        l_strip = line.strip()

        # Le righe vuote vengono scartate qui; eventuale separazione semantica
        # puo essere ricostruita in un passaggio successivo del parser.
        if not l_strip:
            continue

        # Il match per sottostringa rende robusto il filtro a prefissi e suffissi.
        if any(indicator in l_strip.lower() for indicator in noise_list):
            continue

        cleaned_lines.append(line)

    return '\n'.join(cleaned_lines)


def clean_markdown_regex(raw_markdown: str, regex: Iterable[tuple[str, str]]) -> str:
    """
    Applica una sequenza ordinata di sostituzioni regex al markdown.
    L'ordine conta: i parser possono definire prima regole strutturali e poi rifiniture.
    """
    text = raw_markdown
    for pattern, replacement in regex:
        text = re.sub(pattern, replacement, text, flags=re.MULTILINE | re.IGNORECASE)

    return text.strip()


def clean_markdown_by_section_title(text: str, titles_to_remove: list[str]) -> str:
    """
    Rimuove blocchi markdown identificati da un titolo `#`-`######`.
    Una volta intercettato un titolo rumoroso, scarta tutto fino al prossimo
    heading di livello pari o superiore.
    """
    lines = text.splitlines()
    result = []
    skip = False
    current_level = 0

    for i, line in enumerate(lines):
        header_match = re.match(r'^(#{1,6})\s+(.*)', line)
        if header_match:
            level = len(header_match.group(1))
            title = header_match.group(2).strip().lower()

            # Alcuni blocchi Yahoo hanno titoli generici ma una riga successiva
            # che rivela subito la natura video del contenuto.
            next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
            is_video = re.match(r'^\*\s+\d{2}:\d{2}', next_line) or "yahoo finance video" in next_line.lower()

            if skip and level <= current_level and not is_video:
                skip = False

            # Un blocco viene scartato se il titolo corrisponde alla blacklist
            # oppure se il contenuto sottostante e riconosciuto come video.
            is_noise = any(t.lower() in title for t in titles_to_remove) or is_video
            if is_noise:
                skip = True
                current_level = level
                continue

        if not skip:
            result.append(line)

    return '\n'.join(result)
