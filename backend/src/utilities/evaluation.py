import re
from collections import Counter
import jiwer
from rouge_score import rouge_scorer

def remove_markdown(text: str) -> str:
    """
    Rimuove la formattazione markdown. Al fine di valutare solo il contenuto 
    testuale, ignorando elementi di formattazione che non dovrebbero 
    influenzare la valutazione.
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
    # Normalizza spazi e newline, lasciando un singolo spazio.
    text = re.sub(r'\s+', ' ', text).strip()

    return text


def get_token_set(text: str) -> set[str]:
    """
    Estrae i token per le metriche insiemistiche (es. token_level_eval e Jaccard).
    Restituisce un set, quindi l'ordine originale e i duplicati vengono ignorati.
    """
    return set(token.lower() for token in text.split() if token)


def get_token_string(text: str) -> str:
    """
    Normalizza la stringa per le metriche sequenziali (WER e ROUGE).
    Pialla spazi multipli e ritorni a capo mantenendo intatto l'ordine 
    delle parole.
    """
    # L'if token serve a scartare eventuali stringhe vuote prodotte dallo split.
    return " ".join([token.lower() for token in text.split() if token])


# _______________________TOKEN_LEVEL_EVAL (Base Obbligatoria)_______________________

def token_level_eval(parsed_text: str, gold_text: str) -> dict[str, float]:
    """
    Calcola l'intersezione pura dei set di parole, ignorando l'ordine.
    Implementazione richiesta dalle specifiche del progetto.
    """
    cleaned_parsed: str = remove_markdown(parsed_text)

    extracted_tokens: set[str] = get_token_set(cleaned_parsed)
    gs_tokens: set[str] = get_token_set(gold_text)

    # Gestione edge-cases: testi vuoti.
    if not extracted_tokens and not gs_tokens:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0}
    if not extracted_tokens or not gs_tokens:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    intersection: set[str] = extracted_tokens & gs_tokens

    precision: float = len(intersection) / len(extracted_tokens)
    recall: float = len(intersection) / len(gs_tokens)
    
    # Previene ZeroDivisionError se precision e recall sono entrambe 0.
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
    Ignora l'ordine delle parole per quantificare esclusivamente il rumore 
    microscopico (es. tag HTML residui, punteggiatura spuria), garantendo 
    un'esecuzione lineare O(N).
    """
    cleaned_parsed: str = remove_markdown(parsed_text)
    
    # Rimuoviamo gli spazi per concentrare il calcolo solo sul contenuto 
    # e sulla punteggiatura.
    cleaned_parsed = cleaned_parsed.replace(" ", "")
    gold_text_nospaces = gold_text.replace(" ", "")

    # Passando la stringa a Counter, Python crea dietro le quinte una hash map 
    # (dizionario). Le chiavi sono i caratteri e i valori le loro frequenze. 
    # Questo ci permette di calcolare rapidamente l'intersezione e l'unione 
    # dei caratteri, ignorando l'ordine.
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
    Fornisce un singolo valore in [0, 1] utile per valutare la 
    sovrapposizione globale.
    """
    cleaned_parsed: str = remove_markdown(parsed_text)
    
    extracted_tokens: set[str] = get_token_set(cleaned_parsed)
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
    Misura la distanza di Levenshtein (edit distance) a livello di parola.
    Sfrutta la libreria standard 'jiwer'.
    Minore è il valore, più fedele è l'estrazione.
    """
    cleaned_parsed: str = remove_markdown(parsed_text)
    
    str_parsed: str = get_token_string(cleaned_parsed)
    str_gold: str = get_token_string(gold_text)

    # Edge cases: Se il Gold Standard è vuoto, restituiamo il numero 
    # di parole estratte (tutti falsi positivi).
    if not str_gold and not str_parsed: 
        return 0.0
    if not str_gold: 
        return float(len(str_parsed.split()))

    wer_score: float = jiwer.wer(reference=str_gold, hypothesis=str_parsed)
    return round(wer_score, 4)


# _______________________ROUGE-L_______________________

def rouge_l_eval(parsed_text: str, gold_text: str) -> dict[str, float]:
    """
    Valuta l'integrità strutturale del testo estratto calcolando la 
    Longest Common Subsequence (LCS). Utilizza il pacchetto 'rouge-score'.
    """
    cleaned_parsed: str = remove_markdown(parsed_text)
    
    str_parsed: str = get_token_string(cleaned_parsed)
    str_gold: str = get_token_string(gold_text)

    if not str_parsed and not str_gold:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0}
    if not str_parsed or not str_gold:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    # Inizializziamo lo scorer chiedendo solo la variante "rougeL" 
    # (Longest Common Subsequence) e disabilitando lo stemming per 
    # mantenere l'integrità esatta delle parole.
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
    Costruisce e formatta il dizionario finale richiesto dall'endpoint 
    POST /evaluate. Aggiunge le metriche opzionali nel campo 'x_eval'.
    """

    return {
        "token_level_eval": token_level_eval(parsed_text, gold_text),
        "x_eval": {
            "character_level_f1": character_level_eval(
                parsed_text, gold_text
            )["f1"],
            "jaccard_similarity": jaccard_similarity(parsed_text, gold_text),
            "wer": word_error_rate(parsed_text, gold_text),
            "rouge_l_f1": rouge_l_eval(parsed_text, gold_text)["f1"]
        }
    }