FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /project

# Copia prima i requirements per sfruttare la cache di Docker.
COPY frontend/requirements.txt /project/frontend/requirements.txt
RUN pip install --no-cache-dir -r /project/frontend/requirements.txt

# Copia il server frontend e i template Jinja2.
COPY frontend/src /project/frontend/src
COPY frontend/templates /project/frontend/templates

# Porta HTTP richiesta per il frontend.
EXPOSE 8004

# Avvio del server HTML/Jinja2.
CMD ["uvicorn", "frontend:app", "--app-dir", "/project/frontend/src", "--host", "0.0.0.0", "--port", "8004"]
