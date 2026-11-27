# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
#
# TuringTongue CLI image. Build:  docker build -t turingtongue .
# Run:    docker run --rm -e SAPLING_API_KEY turingtongue check --text "Some text" -v
# Stdin:  docker run --rm -i -e GPTZERO_API_KEY turingtongue check - < article.txt

# --- build stage: produce the wheel from the locked sources ----------------------------
FROM python:3.14.10-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.10 /uv /usr/local/bin/uv
WORKDIR /src
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
RUN uv build --wheel --out-dir /dist \
    && uv export --locked --no-dev --no-emit-project --output-file /dist/requirements.txt

# --- runtime stage: wheel only, non-root ------------------------------------------------
FROM python:3.14.10-slim
ARG VERSION=dev
LABEL org.opencontainers.image.title="turingtongue" \
      org.opencontainers.image.description="Ensemble over existing AI-text detection services: HUMAN / AI / NO_VERDICT" \
      org.opencontainers.image.source="https://github.com/marcelpetrick/TuringTongue" \
      org.opencontainers.image.licenses="GPL-3.0-or-later" \
      org.opencontainers.image.version="${VERSION}"
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TURINGTONGUE_NO_DOTENV=1
RUN --mount=type=bind,from=build,source=/dist,target=/dist \
    pip install --require-hashes -r /dist/requirements.txt \
    && pip install --no-deps /dist/*.whl \
    && pip check \
    && useradd --create-home --uid 10001 turingtongue
USER turingtongue
WORKDIR /home/turingtongue
ENTRYPOINT ["turingtongue"]
CMD ["--help"]
