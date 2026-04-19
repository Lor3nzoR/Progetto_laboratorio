import re

def clean_markdown_by_sections(raw_markdown, sections_to_remove):
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