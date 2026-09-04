FROM python:3.11.14-slim-bookworm@sha256:65a93d69fa75478d554f4ad27c85c1e69fa184956261b4301ebaf6dbb0a3543d

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/workspace \
    RUFF_CACHE_DIR=/tmp/ruff-cache

WORKDIR /workspace

COPY control/requirements.validation.lock /tmp/requirements.validation.lock
RUN python -m pip install \
    --no-cache-dir \
    --require-hashes \
    --requirement /tmp/requirements.validation.lock

RUN apt-get update \
    && apt-get install --yes --no-install-recommends curl git jq \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 10001 validator \
    && useradd --create-home --uid 10001 --gid validator validator \
    && chown validator:validator /workspace

COPY --chown=validator:validator . .

USER validator
RUN git init --initial-branch=validation \
    && git add --all \
    && git add --force .env.example .env.schema

CMD ["python", "-m", "pytest", "tests", "-q"]
