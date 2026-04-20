import re

# 1. Legge il tuo testo grezzo copiato da Wikipedia
try:
    with open("testo_grezzo.txt", "r", encoding="utf-8") as f:
        testo = f.read()
except FileNotFoundError:
    print("Errore: Crea un file 'testo_grezzo.txt' e incollaci il testo!")
    exit()

# 2. LA MAGIA DELLE REGEX: Rimuove le note di Wikipedia
# Questa regola cerca: "[" + opzionale "N" e/o spazio + numeri + "]" e li sostituisce con niente ('')
testo = re.sub(r'\[N?\s*\d+\]', '', testo)

# 3. Applica le regole d'oro del JSON per non far arrabbiare VS Code
testo = testo.replace('\\', '\\\\') # Salva eventuali backslash nativi
testo = testo.replace('"', '\\"')   # Neutralizza le virgolette interne
testo = testo.replace('\n', '\\n')  # Trasforma gli 'Invio' testuali in '\n'

# 4. Salva il risultato puro, pronto per essere incollato tra i tuoi " "
with open("testo_pronto.txt", "w", encoding="utf-8") as f:
    f.write(testo)

print("Fatto! Note spazzate via e testo formattato.")
print("Apri 'testo_pronto.txt', seleziona tutto, copia e incolla nel tuo file JSON.")