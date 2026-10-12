# Eigenstaendiges Python-Image statt der HA-Basisimages: keine bashio/s6-Abhaengigkeit,
# gleiche Datei fuer Add-on-Build und lokalen Docker-Test. Start ohne init (config.yaml: init: false).
FROM python:3.13-alpine

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY noah_bridge/ noah_bridge/
CMD ["python", "-m", "noah_bridge"]
