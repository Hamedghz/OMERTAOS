FROM python:3.12-slim@sha256:09f7da3bc104798d0afb40bc08d23ab2da20a76130cec1f2ef170848f5d85217

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=10

WORKDIR /app

COPY control/requirements.docker.txt ./control/requirements.docker.txt

RUN pip install --no-cache-dir --requirement ./control/requirements.docker.txt

COPY control ./control
COPY schemas ./schemas
COPY registry/models ./registry/models
COPY policies ./policies
COPY shared ./shared

EXPOSE 8000 50051

CMD ["python", "-m", "control.app.serve"]
