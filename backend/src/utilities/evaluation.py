"""
Utility di valutazione per confrontare il testo estratto con il gold standard.

Il modulo espone:
- funzioni di normalizzazione preliminare del testo;
- metriche insiemistiche e sequenziali richieste dal progetto;
- un wrapper finale che aggrega i risultati nel formato dell'endpoint.
"""

import re
from collections import Counter

import jiwer
from rouge_score import rouge_scorer


def sanitize_text_for_eval(text: str) -> str:
    """
    Normalizza caratteri invisibili e spazi speciali prima della valutazione.
    Serve a evitare mismatch dovuti ad artefatti Unicode, non al parser.
    """
    if not text:
        return ""

    # Rimuove caratteri invisibili che falserebbero il confronto.
    text = re.sub(r'[\u200B\u200C\u200D\uFEFF\u2060]+', '', text)
    # Normalizza i trattini speciali verso il semplice '-'.
    text = re.sub(r'[\u2011]', '-', text)
    # Uniforma gli spazi non spezzabili agli spazi standard.
    text = re.sub(r'\xa0', ' ', text)
    return text


def remove_markdown(text: str) -> str:
    """
    Rimuove la formattazione markdown per valutare solo il contenuto
    testuale, ignorando elementi grafici che non dovrebbero influenzare
    il confronto con il gold standard.
    """
    # Intestazioni.
    text = re.sub(r'#{1,6}\s*', '', text)
    # Grassetto e corsivo.
    text = re.sub(r'\*{1,2}|_{1,2}', '', text)
    # Link [testo](url) -> testo.
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    # Immagini ![alt](url).
    text = re.sub(r'!\[([^\]]*)\]\([^\)]+\)', '', text)
    # Backtick inline.
    text = re.sub(r'`+', '', text)
    # Linee orizzontali.
    text = re.sub(r'^[-\*]{3,}\s*$', '', text, flags=re.MULTILINE)
    # Citazioni.
    text = re.sub(r'^\s*>\s*', '', text, flags=re.MULTILINE)
    # Separatori tabelle markdown.
    text = re.sub(r'\|[\s\|\-:]+\|', '', text)
    # Doppio trattino isolato.
    text = re.sub(r'\s--\s', ' ', text)
    # Compatta spazi e newline in un singolo spazio lineare.
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def get_token_set(text: str) -> set[str]:
    """
    Estrae i token per le metriche insiemistiche (es. token-level e Jaccard).
    Restituisce un set, quindi ordine e duplicati vengono ignorati.
    """
    return set(token.lower() for token in text.split() if token)


def get_token_string(text: str) -> str:
    """
    Normalizza la stringa per le metriche sequenziali (WER e ROUGE).
    Mantiene l'ordine originale delle parole ma elimina rumore di spacing.
    """
    # I token vuoti prodotti dallo split vengono scartati per evitare doppi spazi.
    return " ".join([token.lower() for token in text.split() if token])


# _______________________TOKEN_LEVEL_EVAL (Base Obbligatoria)_______________________

def token_level_eval(parsed_text: str, gold_text: str) -> dict[str, float]:
    """
    Calcola l'intersezione pura dei set di parole, ignorando l'ordine.
    Implementazione richiesta dalle specifiche del progetto.
    """
    extracted_tokens: set[str] = get_token_set(parsed_text)
    gs_tokens: set[str] = get_token_set(gold_text)

    # Edge case espliciti: due testi vuoti equivalgono a match perfetto.
    if not extracted_tokens and not gs_tokens:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0}
    if not extracted_tokens or not gs_tokens:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    intersection: set[str] = extracted_tokens & gs_tokens

    precision: float = len(intersection) / len(extracted_tokens)
    recall: float = len(intersection) / len(gs_tokens)

    # Previene divisioni per zero quando precision e recall sono entrambe nulle.
    f1: float = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) else 0.0
    )

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


# _______________________CHARACTER_LEVEL_EVAL_______________________

def character_level_eval(parsed_text: str, gold_text: str) -> dict[str, float]:
    """
    Calcola la percentuale di caratteri validi estratti rispetto al totale.
    Ignora l'ordine delle parole per quantificare solo il rumore microscopico
    (es. tag residui o punteggiatura spuria), con costo lineare O(N).
    """
    # Gli spazi vengono esclusi per misurare solo il contenuto effettivo.
    cleaned_parsed = parsed_text.replace(" ", "")
    gold_text_nospaces = gold_text.replace(" ", "")

    # Counter modella il testo come multinsieme di caratteri.
    count_parsed: Counter = Counter(cleaned_parsed)
    count_gold: Counter = Counter(gold_text_nospaces)

    # Somma il minimo tra le frequenze delle occorrenze per ogni carattere.
    char_intersection: int = sum((count_parsed & count_gold).values())
    total_parsed: int = sum(count_parsed.values())
    total_gold: int = sum(count_gold.values())

    if not total_parsed and not total_gold:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0}
    if not total_parsed or not total_gold:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    precision: float = char_intersection / total_parsed
    recall: float = char_intersection / total_gold

    f1: float = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) else 0.0
    )

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


# _______________________JACCARD_SIMILARITY_______________________

def jaccard_similarity(parsed_text: str, gold_text: str) -> float:
    """
    Metrica insiemistica veloce: Intersezione diviso Unione dei token.
    Fornisce un singolo valore in [0, 1] utile per stimare la
    sovrapposizione globale.
    """
    extracted_tokens: set[str] = get_token_set(parsed_text)
    gs_tokens: set[str] = get_token_set(gold_text)

    if not extracted_tokens and not gs_tokens:
        return 1.0
    if not extracted_tokens or not gs_tokens:
        return 0.0

    intersection: set[str] = extracted_tokens & gs_tokens
    union: set[str] = extracted_tokens | gs_tokens

    return round(len(intersection) / len(union), 4)


# _______________________WORD_ERROR_RATE_______________________

def word_error_rate(parsed_text: str, gold_text: str) -> float:
    """
    Misura la distanza di Levenshtein a livello di parola tramite jiwer.
    Minore e il valore, piu fedele e l'estrazione.
    """
    str_parsed: str = get_token_string(parsed_text)
    str_gold: str = get_token_string(gold_text)

    # Se il gold e vuoto, tutte le parole estratte sono falsi positivi.
    if not str_gold and not str_parsed:
        return 0.0
    if not str_gold:
        return float(len(str_parsed.split()))

    wer_score: float = jiwer.wer(reference=str_gold, hypothesis=str_parsed)
    return round(wer_score, 4)


# _______________________ROUGE-L_______________________

def rouge_l_eval(parsed_text: str, gold_text: str) -> dict[str, float]:
    """
    Valuta l'integrita strutturale del testo estratto tramite
    Longest Common Subsequence (ROUGE-L).
    """
    str_parsed: str = get_token_string(parsed_text)
    str_gold: str = get_token_string(gold_text)

    if not str_parsed and not str_gold:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0}
    if not str_parsed or not str_gold:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    # Niente stemming: il confronto deve restare fedele alle parole originali.
    scorer = rouge_scorer.RougeScorer(['rougeL'], use_stemmer=False)
    scores = scorer.score(target=str_gold, prediction=str_parsed)

    return {
        "precision": round(scores['rougeL'].precision, 4),
        "recall": round(scores['rougeL'].recall, 4),
        "f1": round(scores['rougeL'].fmeasure, 4),
    }


# _______________________MAIN WRAPPER_______________________

def evaluate_all(parsed_text: str, gold_text: str) -> dict:
    """
    Costruisce il payload finale richiesto dall'endpoint POST /evaluate.
    Le metriche opzionali vengono raccolte nel campo `x_eval`.
    """
    # Il parsed text va ripulito dal markdown; il gold e gia il riferimento atteso.
    clean_parsed = remove_markdown(sanitize_text_for_eval(parsed_text))
    clean_gold = sanitize_text_for_eval(gold_text)

    return {
        "token_level_eval": token_level_eval(clean_parsed, clean_gold),
        "x_eval": {
            "character_level_f1": character_level_eval(
                clean_parsed, clean_gold
            )["f1"],
            "jaccard_similarity": jaccard_similarity(clean_parsed, clean_gold),
            "wer": word_error_rate(clean_parsed, clean_gold),
            "rouge_l_f1": rouge_l_eval(clean_parsed, clean_gold)["f1"]
        }
    }
