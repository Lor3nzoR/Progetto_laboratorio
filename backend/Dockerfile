FROM python:3.13-slim

# Disabilita i file bytecode `.pyc` e forza il flush immediato dei log Python.
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Directory di lavoro comune del container.
WORKDIR /project

# Installiamo solo i pacchetti di sistema strettamente necessari.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copiamo prima i requirements per sfruttare la cache Docker.
COPY backend/requirements.txt /project/backend/requirements.txt
RUN pip install --no-cache-dir -r /project/backend/requirements.txt

# Copiamo nel container solo i file realmente necessari al backend.
COPY domains.json /project/domains.json
COPY gs_data /project/gs_data
COPY backend/src /project/backend/src

# Porta HTTP esposta dal backend FastAPI.
EXPOSE 8000

# Avvio esplicito di Uvicorn con `--app-dir` per evitare ambiguita' sul path.
CMD ["uvicorn", "src.server:app", "--app-dir", "/project/backend", "--host", "0.0.0.0", "--port", "8000"]# da implementare
