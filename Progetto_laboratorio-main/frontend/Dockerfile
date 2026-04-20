<<<<<<< HEAD
# da implementare
=======
# ===== INIZIO CODICE SCRITTO DA CODEX =====
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /project

COPY frontend/requirements.txt /project/frontend/requirements.txt
RUN pip install --no-cache-dir -r /project/frontend/requirements.txt

COPY frontend/src /project/frontend/src
COPY frontend/templates /project/frontend/templates

EXPOSE 8004

CMD ["uvicorn", "frontend:app", "--app-dir", "/project/frontend/src", "--host", "0.0.0.0", "--port", "8004"]
# ===== FINE CODICE SCRITTO DA CODEX =====
>>>>>>> a6cf71b (Commit iniziale)
