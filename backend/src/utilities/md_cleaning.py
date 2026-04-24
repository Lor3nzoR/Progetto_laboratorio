import re
from typing import Iterable

def clean_markdown_by_sections(raw_markdown: str, sections_to_remove: Iterable[str]) -> str:
    """
    Prende un markdown sporco, rimuove le sezioni indesiderate (blacklist)
    e restituisce un markdown pulito e ricostruito.
    """
    # 1. Pulizia preliminare degli escape comuni del markdown (\", \., \!)
    # Questo rende il testo immediatamente leggibile
    text = raw_markdown.replace('\\"', '"').replace('\\.', '.').replace('\\!', '!')
    
    # 2. Dividiamo il testo basandoci sui titoli di secondo livello (##)
    # Usiamo una regex che cattura il titolo ma mantiene la divisione
    # Il pattern identifica una nuova riga seguita da ## e uno spazio
    sections = re.split(r'\n##\s+', text)
    
    # La prima parte è sempre l'introduzione (testo prima del primo ##)
    clean_parts = []
    intro = sections[0].strip()
    if intro:
        clean_parts.append(intro)
    
    # Prepariamo la blacklist per un confronto case-insensitive
    blacklist = [s.lower().strip() for s in sections_to_remove]
    
    # 3. Analizziamo le sezioni successive
    for section in sections[1:]:
        # Dividiamo il titolo dal contenuto (limite a 1 split sulla prima riga)
        lines = section.split('\n', 1)
        if len(lines) < 2:
            continue
            
        title = lines[0].strip()
        content = lines[1].strip()
        
        # 4. Filtro: se il titolo non è nella blacklist, aggiungiamo la sezione
        if title.lower() not in blacklist:
            # Ricostruiamo la sezione con il suo header originale
            clean_parts.append(f"\n## {title}\n{content}")
    
    # 5. Uniamo tutto con doppi a capo per una formattazione Markdown corretta
    return "\n\n".join(clean_parts)

def clean_markdown_noise(raw_markdown: str, noise_indicators: Iterable[str]) -> str:
    """
    Rimuove righe di rumore, avvisi e righe vuote da un testo Markdown.
    
    Args:
        raw_markdown (str): Il contenuto Markdown grezzo.
        noise_indicators (list): Lista di stringhe che identificano righe da scartare.
        
    Returns:
        str: Il Markdown pulito e ricostruito.
    """
    # 1. Suddividiamo il testo in righe
    lines = raw_markdown.split('\n')
    cleaned_lines = []

    # Trasformiamo gli indicatori in minuscolo per un confronto più sicuro
    noise_list = [str(ind).strip().lower() for ind in noise_indicators]

    for line in lines:
        l_strip = line.strip()
        
        # A. Salta le righe vuote
        if not l_strip:
            continue
            
        # B. Salta se la riga contiene uno degli indicatori (confronto minuscolo)
        # Questo cattura "Modifica wikitesto" anche se l'indicatore è "modifica"
        if any(indicator in l_strip.lower() for indicator in noise_list):
            continue
            
        # Se la riga ha superato tutti i filtri, la teniamo
        cleaned_lines.append(line)

    # 2. Ricongiungiamo le righe con un singolo a capo
    return '\n'.join(cleaned_lines)

def clean_markdown_regex(raw_markdown: str, regex: Iterable[tuple[str, str]]) -> str:
    """
    Pulisce il markdown con regole definite in regex
    """
    text = raw_markdown
    for pattern, replacement in regex:
        text = re.sub(pattern, replacement, text, flags=re.MULTILINE | re.IGNORECASE)

    return text.strip()

def clean_markdown_by_section_title(text: str, titles_to_remove: list[str]) -> str:
    lines = text.splitlines()
    result = []
    skip = False
    current_level = 0

    for i, line in enumerate(lines):
        header_match = re.match(r'^(#{1,6})\s+(.*)', line)
        if header_match:
            level = len(header_match.group(1))
            title = header_match.group(2).strip().lower()

            # Controlla se la riga successiva è un marker video
            next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
            is_video = re.match(r'^\*\s+\d{2}:\d{2}', next_line) or "yahoo finance video" in next_line.lower()

            if skip and level <= current_level and not is_video:
                skip = False

            is_noise = any(t.lower() in title for t in titles_to_remove) or is_video
            if is_noise:
                skip = True
                current_level = level
                continue

        if not skip:
            result.append(line)

    return '\n'.join(result)