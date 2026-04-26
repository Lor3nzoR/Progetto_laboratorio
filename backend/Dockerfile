FROM python:3.13-slim

# Disabilita i file bytecode .pyc e forza il flush immediato dei log Python.
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /project

# Dipendenze di sistema minime; Playwright installa poi Chromium e le sue librerie.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copia prima i requirements per sfruttare la cache dei layer Docker.
COPY backend/requirements.txt /project/backend/requirements.txt
RUN pip install --no-cache-dir -r /project/backend/requirements.txt

# Crawl4AI usa Playwright: il browser deve essere disponibile nel container.
RUN python -m playwright install --with-deps chromium

# Copia solo i file necessari al backend.
COPY domains.json        /project/domains.json
COPY gs_data             /project/gs_data
COPY backend/src         /project/backend/src

EXPOSE 8003

CMD ["uvicorn", "server:app", "--app-dir", "/project/backend/src", "--host", "0.0.0.0", "--port", "8003"]
