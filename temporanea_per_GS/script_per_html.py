import json

# 1. Legge il file in cui hai incollato il testo pulito
try:
    with open("testo_grezzo.txt", "r", encoding="utf-8") as f:
        testo_sporco = f.read()
except FileNotFoundError:
    print("Errore: Crea un file 'testo_grezzo.txt' e incollaci il testo!")
    exit()

# 2. La magia: json.dumps con ensure_ascii=False mantiene le lettere accentate (à, è) in chiaro!
# Fa l'escape solo delle virgolette e degli a capo.
testo_sicuro = json.dumps(testo_sporco, ensure_ascii=False)

# 3. Salva il risultato pronto da copiare
with open("testo_pronto.txt", "w", encoding="utf-8") as f:
    f.write(testo_sicuro)

print("Fatto! Apri 'testo_pronto.txt', seleziona tutto, copia e incolla nel tuo file JSON.")