# Imagem da API para hospedar na nuvem (ver docs/HOSPEDAGEM.md).
FROM python:3.12-slim

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app

# O banco SQLite fica num volume persistente montado em /dados.
ENV VAGACERTA_BANCO=/dados/vagacerta.db
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
