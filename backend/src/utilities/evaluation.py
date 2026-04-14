import re


def remove_markdown(text: str) -> str:
    """Rimuove la formattazione markdown da un testo."""
    # Intestazioni
    text = re.sub(r'#{1,6}\s*', '', text)
    # Grassetto e corsivo
    text = re.sub(r'\*{1,2}|_{1,2}', '', text)
    # Link [testo](url) → testo
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    # Immagini ![alt](url)
    text = re.sub(r'!\[([^\]]*)\]\([^\)]+\)', '', text)
    # Backtick inline
    text = re.sub(r'`+', '', text)
    # Linee orizzontali
    text = re.sub(r'^[-\*]{3,}\s*$', '', text, flags=re.MULTILINE)
    # Citazioni
    text = re.sub(r'^\s*>\s*', '', text, flags=re.MULTILINE)
    # Normalizza spazi e newline
    text = re.sub(r'\s+', ' ', text).strip()

    return text


def tokenize(text: str) -> set[str]:
    """Restituisce l'insieme dei token unici in lowercase."""
    return set(token.lower() for token in text.split() if token)


def token_level_eval(parsed_text: str, gold_text: str) -> dict[str, float]:
    """
    Valuta la qualità del parsing confrontando parsed_text con gold_text a livello di token unici.
    Il parsed_text viene prima pulito dalla formattazione markdown.

    Ritorna un dizionario con precision, recall e f1 (float tra 0 e 1)
    """
    cleaned_parsed: str = remove_markdown(parsed_text)

    tokens_estratti: set[str] = tokenize(cleaned_parsed)
    tokens_gs: set[str] = tokenize(gold_text)

    if not tokens_estratti and not tokens_gs:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0}
    if not tokens_estratti or not tokens_gs:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    intersezione: set[str] = tokens_estratti & tokens_gs

    precision: float = len(intersezione) / len(tokens_estratti)
    recall: float = len(intersezione) / len(tokens_gs)
    f1: float = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }