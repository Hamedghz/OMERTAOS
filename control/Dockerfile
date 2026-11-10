FROM python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=10

WORKDIR /app

COPY control/requirements.docker.txt ./control/requirements.docker.txt

RUN pip install --no-cache-dir --requirement ./control/requirements.docker.txt

COPY control ./control
COPY integrations/providers ./integrations/providers
COPY schemas ./schemas
COPY registry/models ./registry/models
COPY policies ./policies
COPY shared ./shared

EXPOSE 8000 50051

CMD ["python", "-m", "control.app.serve"]
